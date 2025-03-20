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
  
# Sidebar for logo upload and PDF title entry  
with st.sidebar:  
    st.header("Logo & PDF Settings")  
    logo_file = st.file_uploader("Upload Your Logo", type=["png", "jpg", "jpeg"])  
    if logo_file is not None:  
        # Save the logo to a temporary file  
        with open("temp_logo.png", "wb") as f:  
            f.write(logo_file.getbuffer())  
        st.success("Logo uploaded successfully!")  
        st.image("temp_logo.png", width=200)  
    pdf_title_input = st.text_input("Enter the PDF Title", "My mzML Report")  
  
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
    # If peaks is a tuple (e.g., numpy arrays), assume first element is time and second intensities  
    if isinstance(peaks, tuple):  
        times, intensities = peaks  
    else:  
        times = [p.getRT() for p in peaks]  
        intensities = [p.getIntensity() for p in peaks]  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Extract mass spectra data into a DataFrame of top 10 peaks  
    spectra = exp.getSpectra()  
    peaks_data = []  
    for spectrum in spectra:  
        mz_array = spectrum.get_peaks()[0] if isinstance(spectrum.get_peaks(), tuple) else [p.getMZ() for p in spectrum.get_peaks()]  
        intensity_array = spectrum.get_peaks()[1] if isinstance(spectrum.get_peaks(), tuple) else [p.getIntensity() for p in spectrum.get_peaks()]  
        for m, inten in zip(mz_array, intensity_array):  
            peaks_data.append({"m/z": m, "Intensity": inten})  
    if peaks_data:  
        df = pd.DataFrame(peaks_data)  
        df = df.sort_values("Intensity", ascending=False).drop_duplicates("m/z")  
        return df.head(10)  
    else:  
        return pd.DataFrame()  
  
def get_download_link(pdf_buffer, filename):  
    b64 = base64.b64encode(pdf_buffer.read()).decode()  
    href = f'<a class="download-button" href="data:application/octet-stream;base64,{b64}" download="{filename}">Download PDF Report</a>'  
    return href  
  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, pdf_title, target_mass=0, tolerance=0):  
    pdf_buffer = io.BytesIO()  
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter,  
                            rightMargin=72, leftMargin=72,  
                            topMargin=72, bottomMargin=72)  
    styles = getSampleStyleSheet()  
    # Create custom styles with unique names to avoid conflicts  
    custom_title_style = ParagraphStyle(name='CustomTitle', parent=styles['Heading1'],  
                                        fontName='Helvetica-Bold', fontSize=22, leading=26, alignment=TA_CENTER)  
    normal_style = styles['Normal']  
    right_style = ParagraphStyle(name='Right', parent=styles['Normal'], alignment=TA_RIGHT)  
      
    elements = []  
      
    # Add header: Logo on top-right, Title centered.  
    header_table_data = []  
    logo_image = None  
    if os.path.exists("temp_logo.png"):  
        # Use the original logo dimensions, but cap the width if it is too wide.  
        logo_image = RLImage("temp_logo.png")  
        logo_image.drawWidth = min(2*inch, logo_image.drawWidth)  
        logo_image.drawHeight = logo_image.drawHeight * (logo_image.drawWidth / logo_image.imageWidth)  
    header_data = []  
    # Left cell empty, middle cell PDF Title, right cell logo  
    header_data.append(["", f"<b>{pdf_title}</b>", ""])  
    header_table = Table(header_data, colWidths=[2*inch, 3*inch, 2*inch])  
    header_table.setStyle(TableStyle([  
        ('ALIGN', (1,0), (1,0), 'CENTER'),  
        ('VALIGN', (1,0), (1,0), 'MIDDLE')  
    ]))  
    elements.append(header_table)  
    elements.append(Spacer(1, 20))  
      
    if logo_image:  
        # Place the logo at the top right by creating a table with the logo only in the right cell  
        logo_table = Table([["", logo_image]], colWidths=[4*inch, 2*inch])  
        logo_table.setStyle(TableStyle([  
            ('ALIGN', (1,0), (1,0), 'RIGHT'),  
            ('VALIGN', (1,0), (1,0), 'TOP')  
        ]))  
        elements.insert(0, logo_table)  
      
    # Add generation timestamp  
    elements.append(Paragraph(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", right_style))  
    elements.append(Spacer(1, 20))  
      
    # Embed TIC Image  
    if kaleido_available and tic_fig:  
        tic_img_bytes = tic_fig.to_image(format='png', scale=2)  
        tic_image = RLImage(io.BytesIO(tic_img_bytes))  
        tic_image.drawWidth = 6*inch  
        tic_image.drawHeight = 4*inch  
        elements.append(Paragraph("<b>Total Ion Chromatogram</b>", normal_style))  
        elements.append(Spacer(1, 10))  
        elements.append(tic_image)  
        elements.append(Spacer(1, 20))  
      
    # Embed EIC Image if available  
    if kaleido_available and eic_fig:  
        eic_img_bytes = eic_fig.to_image(format='png', scale=2)  
        eic_image = RLImage(io.BytesIO(eic_img_bytes))  
        eic_image.drawWidth = 6*inch  
        eic_image.drawHeight = 4*inch  
        elements.append(Paragraph("<b>Extracted Ion Chromatogram</b>", normal_style))  
        elements.append(Spacer(1, 10))  
        elements.append(eic_image)  
        elements.append(Spacer(1, 20))  
      
    # Embed Mass Spectra Table  
    if not mass_df.empty:  
        data = [mass_df.columns.to_list()] + mass_df.values.tolist()  
        mass_table = Table(data, hAlign='CENTER')  
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
        elements.append(Paragraph("<b>Top 10 Mass Spectra Peaks</b>", normal_style))  
        elements.append(Spacer(1, 10))  
        elements.append(mass_table)  
        elements.append(Spacer(1, 20))  
      
    # Additional details (for example purposes)  
    elements.append(Paragraph(f"Extracted Ion Chromatogram generated for target mass <b>{target_mass}</b> ± <b>{tolerance}</b> m/z.", normal_style))  
    elements.append(Spacer(1,30))  
      
    # Footer  
    elements.append(Paragraph("© 2025 Kapelczak Metabolomics", right_style))  
      
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
        show_points = st.checkbox("Show individual data points on TIC", value=True, key="tic_toggle")  
        mode = "lines+markers" if show_points else "lines"  
      
        tic_fig = go.Figure()  
        tic_fig.add_trace(go.Scatter(  
            x=tic_times,  
            y=tic_intensities,  
            mode=mode,  
            line=dict(color="#2563EB"),  
            marker=dict(color="#D324EB", size=6)  
