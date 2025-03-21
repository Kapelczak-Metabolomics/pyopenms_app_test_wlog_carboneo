# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
import json  
import requests  
import tempfile  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
from PIL import Image  
  
# Try to import kaleido for Plotly image export  
try:  
    import kaleido  
    kaleido_available = True  
except ImportError:  
    kaleido_available = False  
    st.warning("Kaleido package is required for image export. Install it using 'pip install -U kaleido'")  
    st.info("Attempting to install kaleido...")  
    import os  
    os.system("pip install -U kaleido")  
    st.info("Please restart the app after installation.")  
  
# Set page configuration and title  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram, mass spectra data, and generate a modern PDF report using Carbone.io.")  
  
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
  
# Hard-coded Carbone.io API key from your testing account  
CARBONE_API_KEY = "test_eyJhbGciOiJFUzUxMiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIxMTE2MTQ5MDgxNjczMzczNzQxIiwiYXVkIjoiY2FyYm9uZSIsImV4cCI6MjQwNDc3MDUzOSwiZGF0YSI6eyJ0eXBlIjoidGVzdCJ9fQ.AWgZp4j4dhh3oA5odLFaOqC-chL6AsbnEAGi7gbPvDZ6S1Ol_nN7s9H0aoF_YB-bH9mrfGp74Cdz2NorwEIf6TpXASMCAc8dFlwsP6KItMFOx8OnccwGxO3sWHenSkL_IkM3ZpKYDGoY1XxXi7HrAu8SzM8-UbSDop1rG0n7iYCK_CBc"  
  
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
    # For simplicity, use the first chromatogram which is assumed to be the TIC.  
    tic = chromatograms[0]  
    # tic.get_peaks() returns a tuple (times, intensities) as numpy arrays  
    peaks = tic.get_peaks()  
    tic_times = peaks[0].tolist()   # Convert numpy array to list  
    tic_intensities = peaks[1].tolist()  
    return tic_times, tic_intensities  
  
def extract_mass_spectra(exp):  
    # Dummy extraction of mass spectra peaks for demonstration.  
    # In practice, this function should extract real peak data.  
    data = {'m/z': np.linspace(50, 1000, 10), 'Intensity': np.random.randint(100, 1000, 10)}  
    mass_df = pd.DataFrame(data)  
    return mass_df  
  
def fig_to_png_bytes(fig):  
    # Export the plotly figure to PNG using kaleido at high resolution  
    png_bytes = fig.to_image(format="png", scale=2)  
    return png_bytes  
  
def generate_pdf_via_carbone(template_file, data_payload, api_key):  
    # Read the DOCX template as binary  
    with open(template_file, "rb") as f:  
        template_data = f.read()  
    # Create a multipart/form-data payload for Carbone.io  
    files = {  
        "template": ("template.docx", template_data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")  
    }  
    # Carbone endpoint URL for PDF generation  
    url = "https://api.carbone.io/render"  
    headers = {"Authorization": api_key}  
    response = requests.post(url, data={"data": json.dumps(data_payload)}, files=files, headers=headers)  
    if response.status_code != 200:  
        st.error("Failed to generate PDF. Error: " + response.text)  
        return None  
    return response.content  
  
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
        ))  
        tic_fig.update_layout(  
            title=dict(text="Total Ion Chromatogram", x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
            xaxis_title="Retention Time (s)",  
            yaxis_title="Intensity",  
            plot_bgcolor="#FFFFFF",  
            paper_bgcolor="#FFFFFF"  
        )  
        st.plotly_chart(tic_fig)  
      
        mass_df = extract_mass_spectra(experiment)  
        if mass_df.empty:  
            st.warning("No mass spectra data available.")  
        else:  
            st.subheader("Mass Spectra Data (Top 10)")  
            st.dataframe(mass_df.head(10))  
          
        # Convert plotly figure to PNG bytes for embedding in PDF via Carbone.io  
        tic_png = fig_to_png_bytes(tic_fig)  
        tic_png_b64 = base64.b64encode(tic_png).decode("utf-8")  
          
        # Handle logo image sizing while preserving aspect ratio (if available)  
        if logo_file is not None:  
            logo_img = Image.open("temp_logo.png")  
            # Maximum width in inches (e.g., 2 inches) converted to pixels (approx 144 pixels per inch)  
            max_width_pixels = 2 * 144  
            # Check if image width exceeds max width  
            if logo_img.width > max_width_pixels:  
                aspect_ratio = logo_img.height / logo_img.width  
                new_width = max_width_pixels  
                new_height = int(new_width * aspect_ratio)  
                logo_img = logo_img.resize((new_width, new_height))  
            logo_buffer = io.BytesIO()  
            logo_img.save(logo_buffer, format="PNG")  
            logo_data_b64 = base64.b64encode(logo_buffer.getvalue()).decode("utf-8")  
        else:  
            logo_data_b64 = ""  
          
        # Prepare the data payload for Carbone template rendering  
        data_payload = {  
            "title": pdf_title_input,  
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  
            "filename": uploaded_file.name,  
            "tic_image": "data:image/png;base64," + tic_png_b64,  
            "mass_data": mass_df.to_dict(orient="records"),  
            "footer": "© 2025 Kapelczak Metabolomics",  
            "logo_image": "data:image/png;base64," + logo_data_b64 if logo_data_b64 else ""  
        }  
          
        # Assume the DOCX template file is named 'template.docx'  
        template_file = "template.docx"  
        with st.spinner("Generating PDF report via Carbone.io..."):  
            pdf_content = generate_pdf_via_carbone(template_file, data_payload, CARBONE_API_KEY)  
        if pdf_content is not None:  
            st.success("PDF report generated successfully!")  
            # Provide a download link for the generated PDF  
            b64_pdf = base64.b64encode(pdf_content).decode('utf-8')  
            href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{uploaded_file.name.split(".")[0]}_report.pdf"><div class="download-button">Download PDF Report</div></a>'  
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
            st.markdown(href, unsafe_allow_html=True)  
else:  
    st.info("Please upload an mzML file to begin.")  
