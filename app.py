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
from PIL import Image    
  
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
    pdf_title_input = st.text_input("Enter PDF Title", "My PDF Report")    
  
# ----- MS2 Spectral Matching Functions ----- #  
def cosine_similarity(a, b):  
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)  
  
def ms2_matching(query_intensities, library_spectra):  
    results = []  
    for name, lib_intensities in library_spectra.items():  
        # Note: In a more advanced implementation, you would align m/z values and perform proper peak matching.  
        sim = cosine_similarity(np.array(query_intensities), np.array(lib_intensities))  
        results.append((name, sim))  
    # Sort results by similarity score in descending order  
    results.sort(key=lambda x: x[1], reverse=True)  
    return results  
  
# ----- PDF Report Creation Function ----- #  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, target_mass, tolerance, pdf_title):  
    # For simplicity, this creates a PDF report with basic information.  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter)  
    story = []  
    styles = getSampleStyleSheet()  
    title_style = styles['Heading1']  
    story.append(Paragraph(pdf_title, title_style))  
    story.append(Spacer(1, 12))  
    story.append(Paragraph("Filename: " + filename, styles['Normal']))  
    story.append(Paragraph("Target Mass: " + str(target_mass), styles['Normal']))  
    story.append(Paragraph("Tolerance: " + str(tolerance), styles['Normal']))  
    story.append(Spacer(1, 12))  
    # Insert TIC and EIC figures if possible    
    story.append(Paragraph("TIC Plot", styles['Heading2']))  
    tic_img = io.BytesIO(tic_fig.to_image(format='png')) if tic_fig is not None else None  
    if tic_img:  
        story.append(RLImage(tic_img, width=4*inch, height=3*inch))  
    story.append(Spacer(1, 12))  
    story.append(Paragraph("EIC Plot", styles['Heading2']))  
    eic_img = io.BytesIO(eic_fig.to_image(format='png')) if eic_fig is not None else None  
    if eic_img:  
        story.append(RLImage(eic_img, width=4*inch, height=3*inch))  
    story.append(Spacer(1, 12))  
    # Add a table of mass spectra (first 10 rows)    
    story.append(Paragraph("Mass Spectra Data (first 10 rows)", styles['Heading2']))  
    table_data = [mass_df.columns.to_list()] + mass_df.head(10).values.tolist()  
    table = Table(table_data)  
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey),  
                               ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),  
                               ('ALIGN',(0,0),(-1,-1),'CENTER'),  
                               ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),  
                               ('BOTTOMPADDING', (0,0), (-1,0), 12),  
                               ('GRID', (0,0), (-1,-1), 1, colors.black)]))  
    story.append(table)  
    doc.build(story)  
    buffer.seek(0)  
    return buffer  
  
def get_download_link(pdf_buffer, filename_base):  
    b64 = base64.b64encode(pdf_buffer.read()).decode()  
    href = f'<a class=\"download-button\" href=\"data:application/octet-stream;base64,{b64}\" download=\"{filename_base}_report.pdf\">Download PDF Report</a>'  
    return href  
  
# ----- Application Tabs ----- #  
# We use two tabs: one for the original mzML viewing/reporting functionality and one for MS2 spectral matching.  
tabs = st.tabs(["mzML Viewer", "MS2 Spectral Matching"])  
  
# ----- Tab 1: mzML Viewer ----- #  
with tabs[0]:  
    st.header("mzML Chromatogram & Spectra Viewer")  
    uploaded_file = st.file_uploader("Upload mzML file", type=["mzML"])  
    if uploaded_file is not None:  
        st.info("File uploaded, processing...")  
        # Read and process the mzML file (simplified example)  
        exp = MSExperiment()  
        try:  
            MzMLFile().load(uploaded_file, exp)  
            st.success("mzML file successfully loaded!")  
            # Create dummy TIC and EIC plots (replace with actual chromatogram extraction code)  
            tic_fig = go.Figure(data=go.Scatter(x=np.arange(100), y=np.random.rand(100), mode='lines', line=dict(color='#2563EB')))  
            tic_fig.update_layout(title="Total Ion Chromatogram (TIC)")  
            st.plotly_chart(tic_fig, use_container_width=True)  
            eic_fig = go.Figure(data=go.Scatter(x=np.arange(100), y=np.random.rand(100), mode='lines', line=dict(color='#24EB84')))  
            eic_fig.update_layout(title="Extracted Ion Chromatogram (EIC)")  
            st.plotly_chart(eic_fig, use_container_width=True)  
            # Create a dummy dataframe for mass spectra data    
            mass_df = pd.DataFrame({'m/z': np.linspace(100, 1000, 50), 'Intensity': np.random.rand(50)*1e5})  
            st.dataframe(mass_df.head(10))  
            # Dummy target mass and tolerance inputs    
            target_mass = st.number_input("Target Mass", value=500.0)  
            tolerance = st.number_input("Tolerance", value=0.5)  
            st.write("### PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    pdf_buffer = create_pdf_report(filename=uploaded_file.name,  
                                                   tic_fig=tic_fig,  
                                                   eic_fig=eic_fig,  
                                                   mass_df=mass_df,  
                                                   target_mass=target_mass,  
                                                   tolerance=tolerance,  
                                                   pdf_title=pdf_title_input)  
                    download_link = get_download_link(pdf_buffer, uploaded_file.name.split('.')[0])  
                    st.markdown(\"\"\"    
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
                    \"\"\", unsafe_allow_html=True)  
                    st.markdown(download_link, unsafe_allow_html=True)  
                    st.success("PDF report generated successfully! Click the button above to download.")  
        except Exception as e:  
            st.error("Error processing mzML file: " + str(e))  
    else:  
        st
