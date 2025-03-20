# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
  
# Import reportlab components for PDF generation  
from reportlab.lib.pagesizes import letter  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT  
  
# Set page configuration  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram and mass spectra data.")  
  
# -----------------------------------------------  
# Helper functions for processing mzML files  
# -----------------------------------------------  
  
def load_mzml_file(file_bytes):  
    # Create an MSExperiment instance  
    exp = MSExperiment()  
    # Write the bytes to a temporary file since pyopenms requires a filename  
    with open("temp.mzML", "wb") as f:  
        f.write(file_bytes)  
    # Load the mzML file from disk into the experiment object  
    mzml_file = MzMLFile()  
    mzml_file.load("temp.mzML", exp)  
    return exp  
  
def extract_chromatogram(exp):  
    chromatograms = exp.getChromatograms()  
    if len(chromatograms) == 0:  
        return None, None  
    chrom = chromatograms[0]  
    peaks = chrom.get_peaks()  
    # If the returned peaks are a tuple (common with NumPy arrays),  
    # assume peaks[0] is time values and peaks[1] is intensity values.  
    if isinstance(peaks, tuple):  
        times, intensities = peaks  
    else:  
        times = [p.getRT() for p in peaks]  
        intensities = [p.getIntensity() for p in peaks]  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Get all spectra from the experiment  
    spectra = exp.getSpectra()  
    masses = []  
    intensities = []  
    rts = []  
      
    for spectrum in spectra:  
        rt = spectrum.getRT()  
        mz_array, intensity_array = spectrum.get_peaks()  
          
        # Add data to lists  
        for i in range(len(mz_array)):  
            masses.append(mz_array[i])  
            intensities.append(intensity_array[i])  
            rts.append(rt)  
      
    # Create a DataFrame  
    df = pd.DataFrame({  
        'Mass (m/z)': masses,  
        'Retention Time (s)': rts,  
        'Intensity': intensities  
    })  
      
    # Sort by intensity (descending)  
    df = df.sort_values(by='Intensity', ascending=False)  
      
    return df  
  
def extract_mass_peak(df, target_mass, tolerance):  
    # Filter the dataframe for the specified mass within tolerance  
    return df[(df['Mass (m/z)'] >= target_mass - tolerance) &   
              (df['Mass (m/z)'] <= target_mass + tolerance)]  
  
# -----------------------------------------------  
# PDF Generation Functions  
# -----------------------------------------------  
  
def create_modern_pdf_report(filename, tic_data, eic_data=None, mass_df=None, target_mass=None, tolerance=None, logo_path=None):  
    buffer = io.BytesIO()  
      
    # Create the PDF document  
    doc = SimpleDocTemplate(buffer, pagesize=letter,   
                           rightMargin=0.5*inch, leftMargin=0.5*inch,  
                           topMargin=0.5*inch, bottomMargin=0.5*inch)  
      
    # Define styles  
    styles = getSampleStyleSheet()  
      
    # Create custom styles for a modern look  
    title_style = ParagraphStyle(  
        'ModernTitle',  
        parent=styles['Heading1'],  
        fontSize=24,  
        textColor=colors.HexColor('#2563EB'),  
        spaceAfter=12,  
        spaceBefore=12,  
        fontName='Helvetica-Bold'  
    )  
      
    subtitle_style = ParagraphStyle(  
        'ModernSubtitle',  
        parent=styles['Heading2'],  
        fontSize=18,  
        textColor=colors.HexColor('#4B5563'),  
        spaceAfter=10,  
        spaceBefore=10,  
        fontName='Helvetica-Bold'  
    )  
      
    section_style = ParagraphStyle(  
        'ModernSection',  
        parent=styles['Heading3'],  
        fontSize=14,  
        textColor=colors.HexColor('#1F2937'),  
        spaceAfter=8,  
        spaceBefore=8,  
        fontName='Helvetica-Bold'  
    )  
      
    body_style = ParagraphStyle(  
        'ModernBody',  
        parent=styles['Normal'],  
        fontSize=10,  
        textColor=colors.HexColor('#4B5563'),  
        spaceAfter=6,  
        fontName='Helvetica'  
    )  
      
    # Create a list to hold the PDF elements  
    elements = []  
      
    # Add header with logo and title  
    header_data = [  
        [Paragraph(f"mzML Analysis Report", title_style),   
         Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",   
                  ParagraphStyle('Date', parent=body_style, alignment=TA_RIGHT))]  
    ]  
      
    # Create header table  
    header_table = Table(header_data, colWidths=[4*inch, 3*inch])  
    header_table.setStyle(TableStyle([  
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),  
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),  
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),  
        ('TOPPADDING', (0, 0), (-1, -1), 12),  
    ]))  
      
    elements.append(header_table)  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add file information  
    elements.append(Paragraph(f"Filename: {filename}", section_style))  
    elements.append(Spacer(1, 0.1*inch))  
      
    # Add Total Ion Chromatogram section  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", subtitle_style))  
      
    if tic_data is not None and len(tic_data[0]) > 0:  
        # Create a sample of TIC data for the table (first 10 points)  
        tic_sample = [(f"{time:.2f}", f"{intensity:.2f}")   
                      for time, intensity in zip(tic_data[0][:10], tic_data[1][:10])]  
          
        # Create TIC data table  
        tic_table_data = [["Retention Time (s)", "Intensity"]] + tic_sample  
        tic_table = Table(tic_table_data, colWidths=[2.5*inch, 2.5*inch])  
        tic_table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0, 0), (-1, 0), 12),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  
            ('TOPPADDING', (0, 0), (-1, 0), 8),  
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),  
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
        ]))  
          
        elements.append(tic_table)  
        elements.append(Spacer(1, 0.1*inch))  
        elements.append(Paragraph(f"Total data points: {len(tic_data[0])}", body_style))  
    else:  
        elements.append(Paragraph("No TIC data available", body_style))  
      
    elements.append(Spacer(1, 0.2*inch))  
      
    # Add Extracted Ion Chromatogram section if available  
    if eic_data is not None and not eic_data.empty:  
        elements.append(Paragraph(f"Extracted Ion Chromatogram (EIC) - Mass: {target_mass:.4f} ± {tolerance:.4f}", subtitle_style))  
          
        # Create a sample of EIC data for the table (first 10 points)  
        eic_sample = [(f"{row['Retention Time (s)']:.2f}", f"{row['Intensity']:.2f}")   
                      for _, row in eic_data.head(10).iterrows()]  
          
        # Create EIC data table  
        eic_table_data = [["Retention Time (s)", "Intensity"]] + eic_sample  
        eic_table = Table(eic_table_data, colWidths=[2.5*inch, 2.5*inch])  
        eic_table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#24EB84')),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0, 0), (-1, 0), 12),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  
            ('TOPPADDING', (0, 0), (-1, 0), 8),  
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),  
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
        ]))  
          
        elements.append(eic_table)  
        elements.append(Spacer(1, 0.1*inch))  
        elements.append(Paragraph(f"Total data points: {len(eic_data)}", body_style))  
        elements.append(Spacer(1, 0.2*inch))  
      
    # Add Mass Spectra section  
    if mass_df is not None and not mass_df.empty:  
        elements.append(Paragraph("Top Mass Peaks", subtitle_style))  
          
        # Create a sample of mass data for the table (top 15 by intensity)  
        mass_sample = [(f"{row['Mass (m/z)']:.4f}", f"{row['Retention Time (s)']:.2f}", f"{row['Intensity']:.2f}")   
                       for _, row in mass_df.head(15).iterrows()]  
          
        # Create mass data table  
        mass_table_data = [["Mass (m/z)", "Retention Time (s)", "Intensity"]] + mass_sample  
        mass_table = Table(mass_table_data, colWidths=[2*inch, 2*inch, 2*inch])  
        mass_table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D324EB')),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0, 0), (-1, 0), 12),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  
            ('TOPPADDING', (0, 0), (-1, 0), 8),  
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),  
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
        ]))  
          
        elements.append(mass_table)  
        elements.append(Spacer(1, 0.1*inch))  
        elements.append(Paragraph(f"Total unique masses: {len(mass_df['Mass (m/z)'].unique())}", body_style))  
    else:  
        elements.append(Paragraph("No mass spectra data available", body_style))  
      
    # Add footer  
    elements.append(Spacer(1, 0.5*inch))  
    footer_text = "Generated by mzML Chromatogram Viewer | © 2025"  
    elements.append(Paragraph(footer_text,   
                             ParagraphStyle('Footer', parent=body_style,   
                                           alignment=TA_CENTER,   
                                           textColor=colors.HexColor('#9CA3AF'))))  
      
    # Build the PDF  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
def get_download_link(buffer, filename):  
    """Generate a download link for the PDF file"""  
    b64 = base64.b64encode(buffer.read()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}" class="download-button">Download PDF Report</a>'  
    return href  
  
# -----------------------------------------------  
# Logo Upload Section  
# -----------------------------------------------  
st.sidebar.header("Company Logo")  
uploaded_logo = st.sidebar.file_uploader("Upload your logo (optional)", type=["png", "jpg", "jpeg"])  
logo_path = None  
if uploaded_logo is not None:  
    # Save the logo to a temporary file  
    with open("temp_logo.png", "wb") as f:  
        f.write(uploaded_logo.getbuffer())  
    logo_path = "temp_logo.png"  
    st.sidebar.image(uploaded_logo, caption="Your logo", width=200)  
  
# -----------------------------------------------  
# Main App  
# -----------------------------------------------  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Extract and display chromatogram  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        st.subheader("Total Ion Chromatogram (TIC)")  
        show_points = st.checkbox("Show individual data points on TIC", value=True)  
        mode = "lines+markers" if show_points else "lines"  
          
        tic_fig = go.Figure()  
        tic_fig.add_trace(go.Scatter(  
            x=times,  
            y=intensities,  
            mode=mode,  
            line=dict(color="#2563EB"),  
            marker=dict(color="#D324EB", size=6)  
        ))  
        tic_fig.update_layout(  
            title=dict(text="Total Ion Chromatogram", x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
            xaxis_title="Retention Time (s)",  
            yaxis_title="Intensity",  
            xaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
            plot_bgcolor="#FFFFFF",  
            paper_bgcolor="#FFFFFF",  
            font=dict(family="Inter", size=14, color="#171717"),  
            margin=dict(l=60, r=40, t=60, b=60)  
        )  
        st.plotly_chart(tic_fig, use_container_width=True)  
      
    # Extract and display mass spectra data table  
    mass_df = extract_mass_spectra(experiment)  
    if mass_df.empty:  
        st.error("No mass spectra data found in this mzML file.")  
    else:  
        st.subheader("Mass Spectra Data")  
        st.dataframe(mass_df.head(20))  
      
        # User inputs for extracting an ion chromatogram  
        st.markdown("### Extract Ion Chromatogram (EIC)")  
        col1, col2 = st.columns(2)  
        with col1:  
            target_mass = st.number_input("Target Mass (m/z)",   
                                          min_value=float(mass_df["Mass (m/z)"].min()),  
                                          max_value=float(mass_df["Mass (m/z)"].max()),  
                                          value=float(mass_df["Mass (m/z)"].mean()))  
        with col2:  
            tolerance = st.number_input("Tolerance (± m/z)", min_value=0.0001,   
                                        value=0.01, step=0.0001)  
      
        df_peak = extract_mass_peak(mass_df, target_mass, tolerance)  
        if df_peak.empty:  
            st.warning("No mass peaks found for the specified mass and tolerance.")  
            eic_fig = None  
            eic_data = None  
        else:  
            st.success("Mass peaks found: " + str(len(df_peak)))  
            # Group data by Retention Time to create an EIC  
            eic_data = df_peak.groupby("Retention Time (s)")["Intensity"].sum().reset_index()  
            show_points_eic = st.checkbox("Show individual data points on EIC", value=True, key="eic_toggle")  
            mode_eic = "lines+markers" if show_points_eic else "lines"  
      
            eic_fig = go.Figure()  
            eic_fig.add_trace(go.Scatter(  
                x=eic_data["Retention Time (s)"],  
                y=eic_data["Intensity"],  
                mode=mode_eic,  
                line=dict(color="#24EB84"),  
                marker=dict(color="#B2EB24", size=6)  
            ))  
            eic_fig.update_layout(  
                title=dict(text="Extracted Ion Chromatogram", x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
                xaxis_title="Retention Time (s)",  
                yaxis_title="Summed Intensity",  
                xaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
                yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
                plot_bgcolor="#FFFFFF",  
                paper_bgcolor="#FFFFFF",  
                font=dict(family="Inter", size=14, color="#171717"),  
                margin=dict(l=60, r=40, t=60, b=60)  
            )  
            st.plotly_chart(eic_fig, use_container_width=True)  
          
        # PDF Report Generation  
        st.markdown("### Generate Report")  
        if st.button("Generate PDF Report"):  
            with st.spinner("Generating PDF report..."):  
                # Create PDF report  
                pdf_buffer = create_modern_pdf_report(  
                    filename=uploaded_file.name,  
                    tic_data=(times, intensities),  
                    eic_data=eic_data,  
                    mass_df=mass_df,  
                    target_mass=target_mass,  
                    tolerance=tolerance,  
                    logo_path=logo_path  
                )  
                  
                # Create a timestamp for the filename  
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  
                filename = f"mzml_report_{timestamp}.pdf"  
                  
                # Create download link  
                download_link = get_download_link(pdf_buffer, filename)  
                  
                # Display download link with custom styling  
                st.markdown("""  
                <style>  
                .download-button {  
                    display: inline-block;  
                    padding: 0.75em 1.5em;  
                    color: white;  
                    background-color: #2563EB;  
                    border-radius: 6px;  
                    text-decoration: none;  
                    font-weight: bold;  
                    margin-top: 15px;  
                    box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);  
                    transition: all 0.3s ease;  
                }  
                .download-button:hover {  
                    background-color: #1D4ED8;  
                    box-shadow: 0 6px 8px rgba(37, 99, 235, 0.3);  
                    transform: translateY(-2px);  
                }  
                </style>  
                """, unsafe_allow_html=True)  
                  
                st.markdown(download_link, unsafe_allow_html=True)  
                st.success("PDF report generated successfully! Click the button above to download.")  
else:  
    st.info("Please upload an mzML file to begin.")  
