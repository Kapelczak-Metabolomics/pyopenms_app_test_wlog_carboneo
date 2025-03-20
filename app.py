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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
from reportlab.lib.enums import TA_RIGHT  
  
# Try to import kaleido for Plotly image export  
try:  
    import kaleido  
    kaleido_available = True  
except ImportError:  
    kaleido_available = False  
    st.error("Kaleido package is required to export images from Plotly. Install it using 'pip install -U kaleido'.")  
  
# Set page configuration and title  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram, mass spectra data, and generate a modern PDF report.")  
  
# Sidebar for logo upload  
logo_file = st.sidebar.file_uploader("Upload Your Logo", type=["png", "jpg", "jpeg"])  
  
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
    masses, intensities, rts = [], [], []  
    for spectrum in spectra:  
        rt = spectrum.getRT()  
        try:  
            mz_array, intensity_array = spectrum.get_peaks()  
            for i in range(len(mz_array)):  
                masses.append(mz_array[i])  
                intensities.append(intensity_array[i])  
                rts.append(rt)  
        except Exception as e:  
            continue  
    df = pd.DataFrame({  
        'Mass (m/z)': masses,  
        'Intensity': intensities,  
        'Retention Time (s)': rts  
    })  
    return df  
  
def extract_mass_peak(df, target_mass, tolerance):  
    df_peak = df[(df['Mass (m/z)'] >= (target_mass - tolerance)) &  
                 (df['Mass (m/z)'] <= (target_mass + tolerance))]  
    return df_peak  
  
def get_download_link(file_buffer, filename):  
    b64 = base64.b64encode(file_buffer.getvalue()).decode('utf-8')  
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" class="download-button">Download PDF Report</a>'  
    return href  
  
def create_pdf_report(tic_fig, eic_fig, mass_df, target_mass, tolerance, logo_bytes):  
    # Create an in-memory PDF buffer  
    pdf_buffer = io.BytesIO()  
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter,  
                            rightMargin=40, leftMargin=40,  
                            topMargin=60, bottomMargin=40)  
      
    styles = getSampleStyleSheet()  
    styles.add(ParagraphStyle(name='Center', alignment=1, fontSize=18))  
    styles.add(ParagraphStyle(name='Right', alignment=TA_RIGHT, fontSize=10))  
    title_style = styles['Title']  
    normal_style = styles['Normal']  
      
    elements = []  
      
    # Header with logo and title  
    header_data = []  
    if logo_bytes is not None:  
        logo_path = "uploaded_logo.png"  
        with open(logo_path, "wb") as f:  
            f.write(logo_bytes)  
        # Set width while preserving aspect ratio  
        logo_img = RLImage(logo_path, width=1.5*inch, preserveAspectRatio=True)  
        header_data.append(logo_img)  
    else:  
        header_data.append("")  
    header_title = Paragraph("<b>mzML PDF Report</b>", title_style)  
    header_table = Table([[header_title, header_data[0]]], colWidths=[4.5*inch, 2.0*inch])  
    header_table.setStyle(TableStyle([  
        ('ALIGN', (1,0), (1,0), 'RIGHT'),  
        ('VALIGN', (0,0), (-1,-1), 'TOP')  
    ]))  
      
    elements.append(header_table)  
    elements.append(Spacer(1, 12))  
      
    # Report generation time  
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    elements.append(Paragraph("Report generated on: " + now, normal_style))  
    elements.append(Spacer(1, 20))  
      
    # Include Total Ion Chromatogram image  
    if kaleido_available and tic_fig is not None:  
        tic_img_bytes = tic_fig.to_image(format="png")  
        tic_img_buffer = io.BytesIO(tic_img_bytes)  
        tic_rl_img = RLImage(tic_img_buffer, width=6*inch, height=3*inch)  
        elements.append(Paragraph("<b>Total Ion Chromatogram (TIC)</b>", styles['Heading2']))  
        elements.append(tic_rl_img)  
        elements.append(Spacer(1, 20))  
      
    # Include Extracted Ion Chromatogram image (if exists)  
    if kaleido_available and eic_fig is not None:  
        eic_img_bytes = eic_fig.to_image(format="png")  
        eic_img_buffer = io.BytesIO(eic_img_bytes)  
        eic_rl_img = RLImage(eic_img_buffer, width=6*inch, height=3*inch)  
        elements.append(Paragraph("<b>Extracted Ion Chromatogram (EIC)</b>", styles['Heading2']))  
        elements.append(eic_rl_img)  
        elements.append(Spacer(1, 20))  
      
    # Include mass spectra table information (top 10 by intensity)  
    if not mass_df.empty:  
        mass_df_sorted = mass_df.sort_values(by="Intensity", ascending=False).head(10)  
        table_data = [list(mass_df_sorted.columns)]  
        for row in mass_df_sorted.itertuples(index=False):  
            table_data.append([f"{val:.4f}" if isinstance(val, float) else str(val) for val in row])  
        mass_table = Table(table_data)  
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
      
    # Include details about EIC extraction  
    elements.append(Paragraph(f"Extracted Ion Chromatogram was generated for target mass <b>{target_mass}</b> ± <b>{tolerance}</b> m/z.", normal_style))  
      
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
            title=dict(text="Total Ion Chromatogram", x=0.5, xanchor="center",
