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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
  
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
    if not masses:  # Check if lists are empty  
        return pd.DataFrame()  
          
    df = pd.DataFrame({  
        'Mass (m/z)': masses,  
        'Intensity': intensities,  
        'Retention Time (s)': rts  
    })  
      
    # Sort by intensity (descending)  
    df = df.sort_values(by='Intensity', ascending=False)  
      
    return df  
  
def extract_mass_peak(df, target_mass, tolerance):  
    # Filter the DataFrame for the specified mass within tolerance  
    return df[(df['Mass (m/z)'] >= target_mass - tolerance) &   
              (df['Mass (m/z)'] <= target_mass + tolerance)]  
  
# -----------------------------------------------  
# PDF Report Generation Functions  
# -----------------------------------------------  
  
def fig_to_img(fig, width=7.5*inch, height=5*inch):  
    """Convert a plotly figure to a reportlab Image object"""  
    img_bytes = fig.to_image(format="png", width=800, height=500)  
    img_io = io.BytesIO(img_bytes)  
    return Image(img_io, width=width, height=height)  
  
def create_pdf_report(filename, tic_fig, eic_fig=None, mass_df=None, target_mass=None, tolerance=None):  
    """Create a PDF report with chromatogram data"""  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)  
      
    # Create styles  
    styles = getSampleStyleSheet()  
    title_style = ParagraphStyle(  
        'Title',  
        parent=styles['Heading1'],  
        fontSize=18,  
        alignment=1,  # Center alignment  
        spaceAfter=12  
    )  
    subtitle_style = ParagraphStyle(  
        'Subtitle',  
        parent=styles['Heading2'],  
        fontSize=14,  
        spaceAfter=6  
    )  
    normal_style = styles['Normal']  
      
    # Build the PDF content  
    elements = []  
      
    # Title  
    elements.append(Paragraph(f"mzML Analysis Report: {filename}", title_style))  
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Total Ion Chromatogram  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", subtitle_style))  
    elements.append(fig_to_img(tic_fig))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Extracted Ion Chromatogram (if available)  
    if eic_fig is not None and target_mass is not None:  
        elements.append(Paragraph(f"Extracted Ion Chromatogram (EIC) for m/z {target_mass:.4f} ± {tolerance:.4f}", subtitle_style))  
        elements.append(fig_to_img(eic_fig))  
        elements.append(Spacer(1, 0.25*inch))  
      
    # Mass Spectra Data Table (if available)  
    if mass_df is not None and not mass_df.empty:  
        elements.append(Paragraph("Top Mass Peaks by Intensity", subtitle_style))  
          
        # Get top 10 masses by intensity  
        top_masses = mass_df.head(10).reset_index(drop=True)  
          
        # Format the data for the table  
        data = [["#", "Mass (m/z)", "Retention Time (s)", "Intensity"]]  
        for i, row in top_masses.iterrows():  
            data.append([  
                str(i+1),  
                f"{row['Mass (m/z)']:.4f}",  
                f"{row['Retention Time (s)']:.2f}",  
                f"{row['Intensity']:.2e}"  
            ])  
          
        # Create the table  
        table = Table(data, colWidths=[0.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])  
        table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0, 0), (-1, 0), 12),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),  
            ('GRID', (0, 0), (-1, -1), 1, colors.black)  
        ]))  
        elements.append(table)  
      
    # Build the PDF  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
def get_download_link(buffer, filename):  
    """Generate a download link for the PDF"""  
    b64 = base64.b64encode(buffer.read()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}" class="download-button">Download PDF Report</a>'  
    return href  
  
# -----------------------------------------------  
# Main App  
# -----------------------------------------------  
  
# File uploader widget  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
      
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Extract and display total ion chromatogram  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        st.subheader("Total Ion Chromatogram (TIC)")  
        show_points_tic = st.checkbox("Show individual data points on TIC", value=True)  
        mode_tic = "lines+markers" if show_points_tic else "lines"  
          
        tic_fig = go.Figure()  
        tic_fig.add_trace(go.Scatter(  
            x=times,  
            y=intensities,  
            mode=mode_tic,  
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
        with st.spinner("Extracting mass spectra data..."):  
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
            eic_fig = None  
              
            if df_peak.empty:  
                st.warning(f"No mass peaks found for mass {target_mass:.4f} ± {tolerance:.4f}")  
            else:  
                st.success(f"Mass peaks found: {len(df_peak)}")  
                # Group data by Retention Time to create an EIC  
                eic_data = df_peak.groupby("Retention Time (s)")["Intensity"].sum().reset_index()  
                show_points_eic = st.checkbox("Show individual data points on EIC", value=True)  
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
                    title=dict(text=f"Extracted Ion Chromatogram for m/z {target_mass:.4f} ± {tolerance:.4f}",   
                              x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
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
            st.markdown("### Generate PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    # Create the PDF  
                    pdf_buffer = create_pdf_report(  
                        filename=uploaded_file.name,  
                        tic_fig=tic_fig,  
                        eic_fig=eic_fig,  
                        mass_df=mass_df,  
                        target_mass=target_mass,  
                        tolerance=tolerance  
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
                        padding: 0.5em 1em;  
                        color: white;  
                        background-color: #2563EB;  
                        border-radius: 4px;  
                        text-decoration: none;  
                        font-weight: bold;  
                        margin-top: 10px;  
                    }  
                    .download-button:hover {  
                        background-color: #1D4ED8;  
                    }  
                    </style>  
                    """, unsafe_allow_html=True)  
                      
                    st.markdown(download_link, unsafe_allow_html=True)  
                    st.success("PDF report generated successfully! Click the button above to download.")  
else:  
    st.info("Please upload an mzML file to begin.")  
