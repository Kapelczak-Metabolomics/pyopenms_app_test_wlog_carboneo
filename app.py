# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
from datetime import datetime  
import os  
from PIL import Image  
from pyopenms import MSExperiment, MzMLFile  
import tempfile  
  
# Import FPDF for PDF generation  
from fpdf import FPDF  
  
# Try to import kaleido for Plotly image export  
try:  
    import kaleido  
    kaleido_available = True  
except ImportError:  
    kaleido_available = False  
    st.warning("Kaleido package is required for image export. Install it using 'pip install -U kaleido'")  
  
# --- Helper functions for PDF generation ---  
  
# Function to convert hex color to RGB tuple  
def hex_to_rgb(hex_color):  
    hex_color = hex_color.lstrip('#')  
    hlen = len(hex_color)  
    return tuple(int(hex_color[i:i + hlen // 3], 16) for i in range(0, hlen, hlen // 3))  
  
# Custom PDF class using FPDF  
class PDFReport(FPDF):  
    def header(self):  
        self.set_font("Arial", "B", 15)  
        self.cell(0, 10, "Mass Spectrometry Analysis Report", ln=True, align="C")  
        self.ln(5)  
  
    def footer(self):  
        self.set_y(-15)  
        self.set_font("Arial", "I", 8)  
        page_num = "Page " + str(self.page_no())  
        self.cell(0, 10, page_num, 0, 0, "C")  
          
    def chapter_title(self, title):  
        # Title using Julius Blue for text  
        self.set_font("Arial", "B", 12)  
        rgb = hex_to_rgb("#2563EB")  
        self.set_text_color(rgb[0], rgb[1], rgb[2])  
        self.cell(0, 10, title, ln=True)  
        self.ln(5)  
        self.set_text_color(0, 0, 0)  
          
    def chapter_body(self, body):  
        self.set_font("Arial", "", 10)  
        self.multi_cell(0, 5, body)  
        self.ln(5)  
          
    def add_table(self, data, header=True):  
        # Calculate column width based on page width  
        col_width = self.w / len(data[0])  
        # Header row  
        if header:  
            self.set_font("Arial", "B", 10)  
            for item in data[0]:  
                self.cell(col_width, 10, str(item), border=1)  
            self.ln()  
            data = data[1:]  
        # Data rows  
        self.set_font("Arial", "", 10)  
        for row in data:  
            for item in row:  
                self.cell(col_width, 10, str(item), border=1)  
            self.ln()  
  
# Function to generate the PDF report and return it as bytes  
def generate_pdf_report(report_title, report_description, analysis_results, plots, metadata):  
    pdf = PDFReport()  
    pdf.add_page()  
    pdf.set_auto_page_break(auto=True, margin=15)  
      
    # Add report title  
    pdf.set_font("Arial", "B", 16)  
    rgb = hex_to_rgb("#2563EB")  
    pdf.set_text_color(rgb[0], rgb[1], rgb[2])  
    pdf.cell(0, 10, report_title, ln=True, align="C")  
    pdf.ln(5)  
      
    # Reset text color for body  
    pdf.set_text_color(0, 0, 0)  
    pdf.set_font("Arial", "", 12)  
    pdf.multi_cell(0, 5, report_description)  
    pdf.ln(10)  
      
    # Add metadata  
    pdf.chapter_title("Metadata")  
    for key, value in metadata.items():  
        pdf.set_font("Arial", "B", 10)  
        pdf.cell(40, 10, key + ":", border=0)  
        pdf.set_font("Arial", "", 10)  
        pdf.cell(0, 10, str(value), ln=True, border=0)  
    pdf.ln(5)  
      
    # Add analysis results  
    pdf.chapter_title("Analysis Results")  
    table_data = [["Parameter", "Value"]]  
    for key, value in analysis_results.items():  
        table_data.append([key, str(value)])  
    pdf.add_table(table_data)  
    pdf.ln(10)  
      
    # Add plots if available  
    if plots:  
        pdf.chapter_title("Visualizations")  
        for fig in plots:  
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:  
                temp_filename = tmp.name  
                fig.write_image(temp_filename, width=700, height=400)  
            pdf.image(temp_filename, x=10, w=pdf.w - 20)  
            pdf.ln(5)  
            os.unlink(temp_filename)  
      
    # Return the PDF as bytes  
    return pdf.output(dest='S').encode('latin1')  
  
# Function to create a download link for the PDF  
def get_pdf_download_link(pdf_bytes, filename):  
    b64 = base64.b64encode(pdf_bytes).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF Report</a>'  
    return href  
  
# --- Main Streamlit Application ---  
  
def main():  
    st.title("Mass Spectrometry Analysis App")  
      
    # Session state to hold dummy experiment and analysis results  
    if "experiment" not in st.session_state:  
        st.session_state.experiment = None  
    if "analysis_results" not in st.session_state:  
        st.session_state.analysis_results = {}  
    if "plots" not in st.session_state:  
        st.session_state.plots = []  
      
    # Dummy file uploader for demonstration  
    uploaded_file = st.file_uploader("Upload your mass spectrometry data file", type=["mzML", "txt", "csv"])  
    if uploaded_file is not None:  
        st.session_state.experiment = uploaded_file.read()  # Dummy read; replace with actual parsing  
        st.success("Data uploaded successfully!")  
      
    # Dummy analysis trigger for demonstration  
    if st.button("Perform Analysis"):  
        # Create some dummy analysis results and a dummy plot using Plotly  
        st.session_state.analysis_results = {  
            "Analysis Type": "Mass Spectrum",  
            "Retention Time": "123.45 seconds",  
            "Number of Peaks": 250,  
            "Max Intensity": 9876,  
            "m/z Range": "50 - 1500"  
        }  
          
        # Create a simple dummy Plotly plot  
        fig = go.Figure(data=go.Scatter(x=np.linspace(0, 10, 100), y=np.sin(np.linspace(0, 10, 100)), mode='lines', line=dict(color='#2563EB')))  
        fig.update_layout(title="Spectrum Overview", xaxis_title="m/z", yaxis_title="Intensity")  
        st.session_state.plots = [fig]  
          
        st.success("Analysis performed!")  
      
    # Report Generation section  
    st.header("Generate Report")  
    if st.session_state.experiment is None:  
        st.warning("Please upload data first.")  
    elif not st.session_state.analysis_results:  
        st.warning("Please perform analysis first.")  
    else:  
        report_title = st.text_input("Report Title", "Mass Spectrometry Analysis Report")  
        report_description = st.text_area("Report Description", "Analysis of mass spectrometry data.")  
          
        if st.button("Generate PDF Report"):  
            pdf_bytes = generate_pdf_report(  
                report_title,  
                report_description,  
                st.session_state.analysis_results,  
                st.session_state.plots,  
                {"Analysis Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
            )  
            st.markdown(get_pdf_download_link(pdf_bytes, report_title.replace(" ", "_") + ".pdf"), unsafe_allow_html=True)  
  
if __name__ == "__main__":  
    main()  
