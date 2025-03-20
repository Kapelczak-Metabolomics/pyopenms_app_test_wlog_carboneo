# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
  
# Import reportlab components for PDF generation  
from reportlab.lib.pagesizes import letter  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
  
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
    # assume peaks[0] is the time values and peaks[1] is the intensity values.  
    if isinstance(peaks, tuple):  
        times, intensities = peaks  
    else:  
        times = [p.getRT() for p in peaks]  
        intensities = [p.getIntensity() for p in peaks]  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Get all spectra from the experiment  
    spectra = exp.getSpectra()  
    all_masses = []  
    all_intensities = []  
    all_rts = []  
    for spectrum in spectra:  
        rt = spectrum.getRT()  # Retention time  
        mz_array, intensity_array = spectrum.get_peaks()  
        for i in range(len(mz_array)):  
            all_masses.append(mz_array[i])  
            all_intensities.append(intensity_array[i])  
            all_rts.append(rt)  
    if len(all_masses) == 0:  
        return pd.DataFrame()  
    df = pd.DataFrame({  
        'Mass (m/z)': all_masses,  
        'Intensity': all_intensities,  
        'Retention Time (s)': all_rts  
    })  
    return df  
  
def extract_mass_peak(df, target_mass, tolerance):  
    # Filter the dataframe for the target mass within the tolerance  
    df_peak = df[(df['Mass (m/z)'] >= target_mass - tolerance) & (df['Mass (m/z)'] <= target_mass + tolerance)]  
    return df_peak  
  
# -----------------------------------------------  
# Helper function for PDF report creation using ReportLab  
# -----------------------------------------------  
def create_pdf_report(tic_fig, eic_fig, table_data, target_mass=None, tolerance=None):  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter)  
    elements = []  
      
    # Set up styles  
    styles = getSampleStyleSheet()  
    title_style = styles["Title"]  
    normal_style = styles["Normal"]  
      
    # Title Page  
    title_text = "mzML Report"  
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    elements.append(Paragraph(title_text, title_style))  
    elements.append(Spacer(1, 12))  
    elements.append(Paragraph("Generated on: " + timestamp, normal_style))  
    elements.append(Spacer(1, 24))  
      
    # Convert TIC Plotly figure to an image  
    tic_bytes = tic_fig.to_image(format="png")  
    tic_img = Image(io.BytesIO(tic_bytes), width=6*inch, height=4*inch)  
    elements.append(Paragraph("Total Ion Chromatogram (TIC):", normal_style))  
    elements.append(Spacer(1, 12))  
    elements.append(tic_img)  
    elements.append(Spacer(1, 24))  
      
    # If available, convert EIC Plotly figure to an image and add it  
    if eic_fig is not None:  
        eic_bytes = eic_fig.to_image(format="png")  
        eic_img = Image(io.BytesIO(eic_bytes), width=6*inch, height=4*inch)  
        elements.append(Paragraph("Extracted Ion Chromatogram (EIC) for mass {:.4f} ± {:.4f}:".format(target_mass, tolerance), normal_style))  
        elements.append(Spacer(1, 12))  
        elements.append(eic_img)  
        elements.append(Spacer(1, 24))  
      
    # Add table data - showing top 10 rows  
    if not table_data.empty:  
        elements.append(Paragraph("Top 10 Mass Peaks by Intensity:", normal_style))  
        elements.append(Spacer(1, 12))  
          
        # Prepare data for the table (only first 10 rows)  
        table_df = table_data.sort_values(by="Intensity", ascending=False).head(10)  
        table_list = [table_df.columns.tolist()] + table_df.values.tolist()  
        tbl = Table(table_list)  
        tbl.setStyle(TableStyle([  
            ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),  
            ('GRID', (0,0), (-1,-1), 1, colors.black),  
            ('FONTSIZE', (0,0), (-1,-1), 8),  
            ('ALIGN',(0,0),(-1,-1),'CENTER')  
        ]))  
        elements.append(tbl)  
        elements.append(Spacer(1, 24))  
      
    doc.build(elements)  
    pdf_bytes = buffer.getvalue()  
    buffer.close()  
    return pdf_bytes  
  
# -----------------------------------------------  
# Streamlit App Layout  
# -----------------------------------------------  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram and mass data.")  
  
# File uploader widget  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Extract the total ion chromatogram (TIC)  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        st.subheader("Total Ion Chromatogram (TIC)")  
        # Toggle to show individual data points on TIC  
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
            target_mass = st.number_input("Target Mass (m/z)", min_value=float(mass_df["Mass (m/z)"].min()),  
                                          max_value=float(mass_df["Mass (m/z)"].max()), value=float(mass_df["Mass (m/z)"].mean()))  
        with col2:  
            tolerance = st.number_input("Tolerance (± m/z)", min_value=0.0001, value=0.01, step=0.0001)  
      
        df_peak = extract_mass_peak(mass_df, target_mass, tolerance)  
        if df_peak.empty:  
            st.warning("No mass peaks found for the specified mass and tolerance.")  
            eic_fig = None  
        else:  
            st.success("Mass peaks found: {}".format(len(df_peak)))  
            # Group the data by Retention Time to generate an EIC  
            eic_data = df_peak.groupby("Retention Time (s)")["Intensity"].sum().reset_index()  
            # Toggle to show individual data points on EIC  
            show_points_eic = st.checkbox("Show individual data points on EIC", value=True, key="eic_toggle")  
            mode_eic = "lines+
