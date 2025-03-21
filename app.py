# (Start of the app code)  
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
  
# Sidebar for logo upload, PDF title entry, metabolite options and custom metabolite input  
with st.sidebar:  
    st.header("Logo & PDF Settings")  
    logo_file = st.file_uploader("Upload Your Logo", type=["png", "jpg", "jpeg"])  
    if logo_file is not None:  
        # Save the logo to a temporary file   
        with open("temp_logo.png", "wb") as f:  
            f.write(logo_file.getbuffer())  
        st.success("Logo uploaded successfully!")  
        st.image("temp_logo.png", width=200)  
      
    pdf_title_input = st.text_input("Enter PDF Title", value="Mass Spectrometry Report")  
  
    st.header("Metabolite Options")  
    # New widget to select the number of top abundant metabolites for PDF extraction:  
    num_top_metabolites = st.number_input("Select Number of Top Abundant Metabolites", min_value=1, max_value=50, value=10, step=1)  
  
    # New widget to allow users to upload a file containing custom metabolites or enter them manually:  
    custom_metabolite_source = st.radio("Enter Custom Metabolites By", options=["Upload file", "Enter list manually"])  
    custom_metabolites = []  
    if custom_metabolite_source == "Upload file":  
        custom_metabo_file = st.file_uploader("Upload Your Custom Metabolites File (CSV or TXT)", type=["csv", "txt"])  
        if custom_metabo_file is not None:  
            try:  
                # Attempt to read as CSV, fall back to plain text:  
                custom_df = pd.read_csv(custom_metabo_file)  
                # Assume the first column holds metabolite names or m/z values  
                custom_metabolites = custom_df.iloc[:, 0].tolist()  
            except Exception as e:  
                custom_metabolites = [line.strip() for line in custom_metabo_file.getvalue().decode("utf-8").splitlines() if line.strip() != ""]  
    else:  
        custom_metabo_str = st.text_area("Enter custom metabolites (separated by commas)", value="")  
        if custom_metabo_str:  
            custom_metabolites = [x.strip() for x in custom_metabo_str.split(",") if x.strip() != ""]  
  
# Main file uploader for mzML file processing  
uploaded_file = st.file_uploader("Upload an mzML file", type=["mzML"])  
if uploaded_file is not None:  
    # Load and process the mzML file (implementation not shown for brevity)  
    # Assume processing gives us: tic_fig, eic_fig, mass_df, target_mass, tolerance etc.  
    # For the purpose of this code snippet, we assume these are already defined.  
    st.info("Processing uploaded mzML file...")  
  
    # Example: Generate TIC figure (your implementation here)  
    # tic_fig = some_function_to_generate_TIC(uploaded_file)  
      
    # Example: Filter mass_df to top abundant metabolites using the selected number  
    # mass_df is assumed to be a DataFrame with metabolites sorted by abundance.  
    top_metabolites_df = mass_df.head(num_top_metabolites) if 'mass_df' in locals() else pd.DataFrame()  
  
    # Create the combined custom metabolite extraction graph  
    if custom_metabolites:  
        # Here, assume get_chromatogram() is a helper function that returns a Plotly trace for given metabolite.  
        combined_fig = go.Figure()  
        colors_list = ["#2563EB", "#24EB84", "#B2EB24", "#EB3424", "#D324EB"]  
        for i, metab in enumerate(custom_metabolites):  
            # Replace with your actual extraction function; for demonstration, create a dummy trace.  
            trace = go.Scatter(x=np.linspace(0, 100, 200), y=np.sin(np.linspace(0, 10, 200) + i),  
                               mode="lines", name="Custom: " + str(metab),  
                               line=dict(color=colors_list[i % len(colors_list)]))  
            combined_fig.add_trace(trace)  
        combined_fig.update_layout(title="Combined Chromatogram for Custom Metabolites",  
                                   xaxis_title="Retention Time",  
                                   yaxis_title="Intensity")  
        st.plotly_chart(combined_fig, use_container_width=True)  
      
    st.header("### PDF Report")  
    if st.button("Generate PDF Report"):  
        with st.spinner("Generating PDF report..."):  
            # Generate PDF report using the top metabolites and plots   
            # Here, pass the top_metabolites_df to the PDF generation function:  
            pdf_buffer = create_pdf_report(  
                filename=uploaded_file.name,  
                tic_fig=tic_fig,  
                eic_fig=eic_fig,  
                mass_df=top_metabolites_df,  # now using the selected top N metabolites  
                target_mass=target_mass,  
                tolerance=tolerance,  
                pdf_title=pdf_title_input  
            )  
              
            # Create download link (assuming get_download_link is defined)  
            download_link = get_download_link(pdf_buffer, uploaded_file.name.split('.')[0])  
              
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
