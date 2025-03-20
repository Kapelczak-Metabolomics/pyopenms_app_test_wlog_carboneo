# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
import os  
  
# Import reportlab components for PDF generation  
from reportlab.lib.pagesizes import letter  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT  
  
# Try to import kaleido for Plotly image export  
try:  
    import kaleido  
    kaleido_available = True  
except ImportError:  
    kaleido_available = False  
    st.warning("Kaleido package is required for image export. Install it using 'pip install -U kaleido'")  
    st.info("Attempting to install kaleido...")  
    os.system("pip install -U kaleido")  
    st.info("Please restart the app after installation.")  
  
# Set page configuration and title  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram, mass spectra data, and generate a modern PDF report.")  
  
# Sidebar for logo upload  
with st.sidebar:  
    st.header("Logo Settings")  
    logo_file = st.file_uploader("Upload Your Logo", type=["png", "jpg", "jpeg"])  
    if logo_file is not None:  
        # Save the logo to a temporary file  
        with open("temp_logo.png", "wb") as f:  
            f.write(logo_file.getbuffer())  
        st.success("Logo uploaded successfully!")  
        st.image("temp_logo.png", width=200)  
  
# -----------------------------------------------  
# Helper functions for processing mzML files  
# -----------------------------------------------  
  
def load_mzml_file(file_bytes):  
    exp = MSExperiment()  
    with open("temp.mzML", "wb") as f:  
        f.write(file_bytes)  
    mzml_file = MzMLFile()  
    mzml_file.load("temp.mzML", exp)  
    return exp  
  
def extract_chromatogram(exp):  
    chromatograms = exp.getChromatograms()  
    if len(chromatograms) == 0:  
        return None, None  
    chrom = chromatograms[0]  
    peaks = chrom.get_peaks()  
    if isinstance(peaks, tuple):  
        times, intensities = peaks  
    else:  
        times = [p.getRT() for p in peaks]  
        intensities = [p.getIntensity() for p in peaks]  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    spectra = exp.getSpectra()  
    masses = []  
    intensities = []  
    rts = []  
      
    for spectrum in spectra:  
        rt = spectrum.getRT()  
        mz_array, intensity_array = spectrum.get_peaks()  
          
        for i in range(len(mz_array)):  
            masses.append(mz_array[i])  
            intensities.append(intensity_array[i])  
            rts.append(rt)  
      
    if not masses:  
        return pd.DataFrame()  
      
    df = pd.DataFrame({  
        "Mass (m/z)": masses,  
        "Intensity": intensities,  
        "Retention Time (s)": rts  
    })  
      
    return df  
  
def extract_mass_peak(df, target_mass, tolerance):  
    return df[(df["Mass (m/z)"] >= target_mass - tolerance) &   
              (df["Mass (m/z)"] <= target_mass + tolerance)]  
  
# -----------------------------------------------  
# PDF Generation Functions  
# -----------------------------------------------  
  
def get_download_link(buffer, filename):  
    """Generate a download link for a PDF file."""  
    b64 = base64.b64encode(buffer.read()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" class="download-button" download="{filename}">Download PDF Report</a>'  
    return href  
  
def create_pdf_report(filename, tic_fig, eic_fig=None, mass_df=None, target_mass=None, tolerance=None):  
    """Create a PDF report with chromatogram images and data tables."""  
    pdf_buffer = io.BytesIO()  
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)  
      
    # Create styles  
    styles = getSampleStyleSheet()  
    styles.add(ParagraphStyle(name='Title',   
                             fontName='Helvetica-Bold',   
                             fontSize=18,   
                             leading=22,   
                             textColor=colors.HexColor("#2563EB")))  
    styles.add(ParagraphStyle(name='Heading2',   
                             fontName='Helvetica-Bold',   
                             fontSize=14,   
                             leading=18,   
                             textColor=colors.HexColor("#2563EB"),  
                             spaceAfter=10))  
    styles.add(ParagraphStyle(name='Right',   
                             fontName='Helvetica',   
                             fontSize=10,   
                             alignment=TA_RIGHT))  
    styles.add(ParagraphStyle(name='Center',   
                             fontName='Helvetica',   
                             fontSize=12,   
                             alignment=TA_CENTER))  
      
    normal_style = ParagraphStyle(name='Normal',   
                                 fontName='Helvetica',   
                                 fontSize=12,   
                                 leading=14)  
      
    # Elements to add to the PDF  
    elements = []  
      
    # Create a header table with logo  
    logo_path = "temp_logo.png" if os.path.exists("temp_logo.png") else None  
      
    if logo_path:  
        # Create a header with logo  
        logo_img = RLImage(logo_path, width=1.5*inch, height=0.75*inch)  
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
          
        header_data = [[Paragraph(f"<b>{filename}</b>", styles['Title']), logo_img],  
                      [Paragraph(f"Generated: {timestamp}", normal_style), ""]]  
          
        header_table = Table(header_data, colWidths=[4*inch, 2*inch])  
        header_table.setStyle(TableStyle([  
            ('VALIGN', (0,0), (-1,-1), 'TOP'),  
            ('ALIGN', (1,0), (1,0), 'RIGHT'),  
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),  
        ]))  
        elements.append(header_table)  
    else:  
        # Header without logo  
        elements.append(Paragraph(f"<b>{filename}</b>", styles['Title']))  
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))  
      
    elements.append(Spacer(1, 20))  
      
    # Add TIC image  
    if tic_fig and kaleido_available:  
        tic_img_path = "tic_plot.png"  
        tic_fig.write_image(tic_img_path, width=700, height=400, scale=2)  
        elements.append(Paragraph("<b>Total Ion Chromatogram</b>", styles['Heading2']))  
        elements.append(RLImage(tic_img_path, width=6.5*inch, height=3.5*inch))  
        elements.append(Spacer(1, 10))  
      
    # Add EIC image if available  
    if eic_fig and kaleido_available:  
        eic_img_path = "eic_plot.png"  
        eic_fig.write_image(eic_img_path, width=700, height=400, scale=2)  
        elements.append(Paragraph(f"<b>Extracted Ion Chromatogram (m/z {target_mass:.4f} ± {tolerance:.4f})</b>", styles['Heading2']))  
        elements.append(RLImage(eic_img_path, width=6.5*inch, height=3.5*inch))  
        elements.append(Spacer(1, 10))  
      
    # Add mass spectra data table if available  
    if mass_df is not None and not mass_df.empty:  
        # Get top 10 peaks by intensity  
        top_peaks = mass_df.sort_values("Intensity", ascending=False).head(10)  
          
        # Create table data  
        table_data = [["Mass (m/z)", "Intensity", "Retention Time (s)"]]  
        for _, row in top_peaks.iterrows():  
            table_data.append([  
                f"{row['Mass (m/z)']:.4f}",  
                f"{row['Intensity']:.2f}",  
                f"{row['Retention Time (s)']:.2f}"  
            ])  
          
        # Create table  
        mass_table = Table(table_data, colWidths=[2*inch, 2*inch, 2*inch])  
        mass_table.setStyle(TableStyle([  
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2563EB")),  
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),  
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),  
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0,0), (-1,0), 12),  
            ('BOTTOMPADDING', (0,0), (-1,0), 8),  
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),  
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey)  
        ]))  
        elements.append(Paragraph("<b>Top 10 Mass Spectra Peaks</b>", styles['Heading2']))  
        elements.append(mass_table)  
        elements.append(Spacer(1, 20))  
      
    # Include details about EIC extraction if applicable  
    if target_mass and tolerance:  
        elements.append(Paragraph(f"Extracted Ion Chromatogram was generated for target mass <b>{target_mass:.4f}</b> ± <b>{tolerance:.4f}</b> m/z.", normal_style))  
      
    # Footer  
    elements.append(Spacer(1, 30))  
    elements.append(Paragraph("© 2025 Your Company Name", styles['Right']))  
      
    # Build PDF  
    doc.build(elements)  
    pdf_buffer.seek(0)  
      
    return pdf_buffer  
  
# -----------------------------------------------  
# Main Streamlit app  
# -----------------------------------------------  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    tic_times, tic_intensities = extract_chromatogram(experiment)  
    if tic_times is None or tic_intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        # Toggle for data point visualization in TIC plot  
        show_points = st.checkbox("Show individual data points on TIC", value=True, key="tic_toggle")  
        mode = "lines+markers" if show_points else "lines"  
      
        tic_fig = go.Figure()  
        tic_fig.add_trace(go.Scatter(  
            x=tic_times,  
            y=tic_intensities,  
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
            else:  
                st.success(f"Mass peaks found: {len(df_peak)}")  
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
            st.markdown("### Generate PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    # Create PDF report  
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
