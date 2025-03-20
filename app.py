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
        try:  
            mz_array, intensity_array = spectrum.get_peaks()  
        except Exception:  
            continue  
        # Record all mass peaks and their corresponding intensity and retention time  
        for i in range(len(mz_array)):  
            masses.append(mz_array[i])  
            intensities.append(intensity_array[i])  
            rts.append(rt)  
    df = pd.DataFrame({  
        "Mass (m/z)": masses,  
        "Intensity": intensities,  
        "Retention Time (s)": rts  
    })  
    return df  
  
def extract_mass_peak(df, target_mass, tol):  
    # Filter the dataframe to get only the peaks with Mass within the specified tolerance  
    df_peak = df[(df["Mass (m/z)"] >= target_mass - tol) & (df["Mass (m/z)"] <= target_mass + tol)]  
    return df_peak  
  
def get_plot_image_bytes(fig):  
    # Get plot image as PNG bytes using Plotly  
    img_bytes = fig.to_image(format="png")  
    return img_bytes  
  
def create_pdf_report(tic_fig, eic_fig, mass_table, filename):  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter)  
    elements = []  
    styles = getSampleStyleSheet()  
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#171717"))  
    normal_style = styles["Normal"]  
  
    # Add title and timestamp  
    elements.append(Paragraph("mzML Report", title_style))  
    elements.append(Spacer(1, 12))  
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    elements.append(Paragraph("Report generated at: " + timestamp, normal_style))  
    elements.append(Spacer(1, 24))  
  
    # Add TIC image  
    tic_img_bytes = get_plot_image_bytes(tic_fig)  
    tic_img = Image(io.BytesIO(tic_img_bytes), width=6*inch, height=4*inch)  
    elements.append(Paragraph("Total Ion Chromatogram", styles["Heading2"]))  
    elements.append(tic_img)  
    elements.append(Spacer(1, 12))  
  
    # Add EIC image if available  
    if eic_fig:  
        eic_img_bytes = get_plot_image_bytes(eic_fig)  
        eic_img = Image(io.BytesIO(eic_img_bytes), width=6*inch, height=4*inch)  
        elements.append(Paragraph("Extracted Ion Chromatogram", styles["Heading2"]))  
        elements.append(eic_img)  
        elements.append(Spacer(1, 12))  
  
    # Add mass table data  
    if not mass_table.empty:  
        elements.append(Paragraph("Mass Spectra Data (Top 10 peaks by intensity)", styles["Heading2"]))  
        tbl_data = [list(mass_table.columns)]  
        for row in mass_table.head(10).itertuples(index=False):  
            tbl_data.append(list(row))  
        t = Table(tbl_data)  
        t.setStyle(TableStyle([  
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2563EB")),  
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),  
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),  
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),  
            ('BOX', (0,0), (-1,-1), 0.25, colors.black)  
        ]))  
        elements.append(t)  
        elements.append(Spacer(1, 12))  
  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
def get_download_link(pdf_buffer, filename):  
    # Encode PDF to base64  
    b64 = base64.b64encode(pdf_buffer.read()).decode()  
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download PDF Report</a>'  
    return href  
  
# -----------------------------------------------  
# Streamlit App UI  
# -----------------------------------------------  
  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view and analyze its content, then generate a PDF report.")  
  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Display the Total Ion Chromatogram (TIC)  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        show_points_tic = st.checkbox("Show individual data points on TIC", value=True, key="tic_toggle")  
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
      
    # Extract mass spectra data and display as a table  
    mass_df = extract_mass_spectra(experiment)  
    if mass_df.empty:  
        st.error("No mass spectra data found in this mzML file.")  
    else:  
        st.subheader("Mass Spectra Data")  
        st.dataframe(mass_df.head(20))  
      
        # User inputs for extracting an ion chromatogram (EIC)  
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
                paper
