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
  
# Import FPDF for PDF generation  
from fpdf import FPDF  
import tempfile  
  
# Try to import kaleido for Plotly image export      
try:      
    import kaleido      
    kaleido_available = True      
except ImportError:      
    kaleido_available = False      
    st.warning("Kaleido package is required for image export. Install it using 'pip install -U kaleido'")  
  
# Define a custom PDF class inheriting from FPDF  
class PDFReport(FPDF):  
    def header(self):  
        # Set font for header  
        self.set_font("Arial", "B", 15)  
        # Title  
        self.cell(0, 10, "Mass Spectrometry Analysis Report", ln=True, align="C")  
        # Line break  
        self.ln(5)  
  
    def footer(self):  
        # Position at 1.5 cm from bottom  
        self.set_y(-15)  
        self.set_font("Arial", "I", 8)  
        # Page number  
        page_num = "Page " + str(self.page_no())  
        self.cell(0, 10, page_num, 0, 0, "C")  
          
    def chapter_title(self, title):  
        # Set font for chapter title  
        self.set_font("Arial", "B", 12)  
        # Convert hex color to RGB  
        rgb = hex_to_rgb("#2563EB")  
        self.set_text_color(rgb[0], rgb[1], rgb[2])  
        # Add title  
        self.cell(0, 10, title, ln=True)  
        # Line break  
        self.ln(5)  
        # Reset text color  
        self.set_text_color(0, 0, 0)  
          
    def chapter_body(self, body):  
        # Set font for chapter body  
        self.set_font("Arial", "", 10)  
        # Add body text  
        self.multi_cell(0, 5, body)  
        # Line break  
        self.ln(5)  
          
    def add_table(self, data, header=True):  
        # Calculate column width to fit page  
        col_width = self.w / len(data[0])  
        # Set font for table  
        self.set_font("Arial", "B", 10)  
          
        # Add header row with background color  
        if header:  
            self.set_fill_color(37, 99, 235)  # #2563EB in RGB  
            self.set_text_color(255, 255, 255)  # White text  
            for i, item in enumerate(data[0]):  
                self.cell(col_width, 10, str(item), 1, 0, "C", True)  
            self.ln()  
              
        # Add data rows  
        self.set_font("Arial", "", 10)  
        self.set_text_color(0, 0, 0)  # Black text  
          
        for i, row in enumerate(data[1:] if header else data):  
            # Alternate row background colors  
            fill = i % 2 == 0  
            if fill:  
                self.set_fill_color(248, 249, 250)  # #F8F9FA in RGB  
            else:  
                self.set_fill_color(255, 255, 255)  # White  
                  
            for item in row:  
                self.cell(col_width, 10, str(item), 1, 0, "C", fill)  
            self.ln()  
  
# Function to convert hex color to RGB tuple  
def hex_to_rgb(hex_color):  
    hex_color = hex_color.lstrip('#')  
    hlen = len(hex_color)  
    return tuple(int(hex_color[i:i+hlen//3], 16) for i in range(0, hlen, hlen//3))  
  
# Function to generate a PDF report  
def generate_pdf_report(title, description, experiment_data, plots, parameters):  
    pdf = PDFReport()  
    pdf.add_page()  
    pdf.set_auto_page_break(auto=True, margin=15)  
      
    # Add report metadata  
    pdf.chapter_title("Report Information")  
    pdf.chapter_body(f"Title: {title}\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")  
      
    # Add experiment description  
    pdf.chapter_title("Experiment Description")  
    pdf.chapter_body(description)  
      
    # Add parameters section  
    pdf.chapter_title("Analysis Parameters")  
    param_text = ""  
    for key, value in parameters.items():  
        param_text += f"{key}: {value}\n"  
    pdf.chapter_body(param_text)  
      
    # Add experiment data  
    if experiment_data:  
        pdf.chapter_title("Experiment Data Summary")  
        # Convert experiment data to a table format  
        table_data = [["Parameter", "Value"]]  
        for key, value in experiment_data.items():  
            table_data.append([key, str(value)])  
        pdf.add_table(table_data)  
      
    # Add plots  
    if plots:  
        pdf.chapter_title("Analysis Plots")  
        for i, plot in enumerate(plots):  
            # Save plot to a temporary file  
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')  
            temp_file.close()  
              
            # Save the plot as an image  
            if isinstance(plot, go.Figure):  
                plot.write_image(temp_file.name, width=700, height=400)  
            else:  
                # Assume it's a PIL Image or similar  
                plot.save(temp_file.name)  
              
            # Add the image to the PDF  
            pdf.image(temp_file.name, x=10, w=190)  
            pdf.ln(5)  
              
            # Clean up the temporary file  
            os.unlink(temp_file.name)  
      
    # Generate the PDF in memory  
    pdf_output = io.BytesIO()  
    pdf.output(pdf_output)  
    pdf_output.seek(0)  
      
    return pdf_output  
  
# Function to create a download link for the PDF  
def get_pdf_download_link(pdf_bytes, filename="report.pdf", text="Download PDF Report"):  
    b64 = base64.b64encode(pdf_bytes.read()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'  
    return href  
  
# Streamlit app  
def main():  
    st.set_page_config(page_title="Mass Spectrometry Analysis Tool", layout="wide")  
      
    st.title("Mass Spectrometry Analysis Tool")  
      
    # Sidebar for navigation  
    st.sidebar.title("Navigation")  
    page = st.sidebar.radio("Go to", ["Data Upload", "Analysis", "Report Generation"])  
      
    # Initialize session state  
    if 'experiment' not in st.session_state:  
        st.session_state.experiment = None  
    if 'analysis_results' not in st.session_state:  
        st.session_state.analysis_results = {}  
    if 'plots' not in st.session_state:  
        st.session_state.plots = []  
      
    if page == "Data Upload":  
        st.header("Upload Mass Spectrometry Data")  
          
        uploaded_file = st.file_uploader("Choose an mzML file", type=['mzml'])  
          
        if uploaded_file is not None:  
            # Save the uploaded file temporarily  
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mzml') as tmp_file:  
                tmp_file.write(uploaded_file.getvalue())  
                tmp_path = tmp_file.name  
              
            # Load the experiment  
            experiment = MSExperiment()  
            file = MzMLFile()  
            file.load(tmp_path, experiment)  
              
            # Clean up the temporary file  
            os.unlink(tmp_path)  
              
            # Store the experiment in session state  
            st.session_state.experiment = experiment  
              
            # Display basic information  
            st.success(f"File loaded successfully: {uploaded_file.name}")  
            st.write(f"Number of spectra: {experiment.size()}")  
              
            if experiment.size() > 0:  
                spectrum = experiment[0]  
                st.write(f"First spectrum MS level: {spectrum.getMSLevel()}")  
                st.write(f"First spectrum RT: {spectrum.getRT()} seconds")  
      
    elif page == "Analysis":  
        st.header("Data Analysis")  
          
        if st.session_state.experiment is None:  
            st.warning("Please upload data first.")  
            return  
          
        experiment = st.session_state.experiment  
          
        # Analysis options  
        st.subheader("Analysis Parameters")  
          
        analysis_type = st.selectbox(  
            "Select Analysis Type",  
            ["TIC (Total Ion Chromatogram)", "Base Peak Chromatogram", "Mass Spectrum at RT"]  
        )  
          
        if analysis_type == "TIC (Total Ion Chromatogram)":  
            # Generate TIC  
            rts = []  
            intensities = []  
              
            for spectrum in experiment:  
                if spectrum.getMSLevel() == 1:  # MS1 only  
                    rts.append(spectrum.getRT())  
                    intensities.append(sum(spectrum.get_peaks()[1]))  
              
            # Create plot  
            fig = go.Figure()  
            fig.add_trace(go.Scatter(  
                x=rts,  
                y=intensities,  
                mode='lines',  
                line=dict(color='#2563EB', width=2),  
                name='TIC'  
            ))  
              
            fig.update_layout(  
                title="Total Ion Chromatogram",  
                xaxis_title="Retention Time (seconds)",  
                yaxis_title="Intensity",  
                template="plotly_white"  
            )  
              
            st.plotly_chart(fig, use_container_width=True)  
              
            # Store results  
            st.session_state.analysis_results = {  
                "Analysis Type": "TIC",  
                "Number of Points": len(rts),  
                "Max Intensity": max(intensities) if intensities else 0,  
                "RT Range": f"{min(rts) if rts else 0} - {max(rts) if rts else 0} seconds"  
            }  
              
            # Store plot  
            st.session_state.plots = [fig]  
          
        elif analysis_type == "Base Peak Chromatogram":  
            # Generate Base Peak Chromatogram  
            rts = []  
            intensities = []  
              
            for spectrum in experiment:  
                if spectrum.getMSLevel() == 1:  # MS1 only  
                    peaks = spectrum.get_peaks()  
                    if len(peaks[1]) > 0:  
                        rts.append(spectrum.getRT())  
                        intensities.append(max(peaks[1]))  
              
            # Create plot  
            fig = go.Figure()  
            fig.add_trace(go.Scatter(  
                x=rts,  
                y=intensities,  
                mode='lines',  
                line=dict(color='#2563EB', width=2),  
                name='Base Peak'  
            ))  
              
            fig.update_layout(  
                title="Base Peak Chromatogram",  
                xaxis_title="Retention Time (seconds)",  
                yaxis_title="Intensity",  
                template="plotly_white"  
            )  
              
            st.plotly_chart(fig, use_container_width=True)  
              
            # Store results  
            st.session_state.analysis_results = {  
                "Analysis Type": "Base Peak Chromatogram",  
                "Number of Points": len(rts),  
                "Max Intensity": max(intensities) if intensities else 0,  
                "RT Range": f"{min(rts) if rts else 0} - {max(rts) if rts else 0} seconds"  
            }  
              
            # Store plot  
            st.session_state.plots = [fig]  
          
        elif analysis_type == "Mass Spectrum at RT":  
            # RT selection  
            min_rt = min([spectrum.getRT() for spectrum in experiment if spectrum.getMSLevel() == 1])  
            max_rt = max([spectrum.getRT() for spectrum in experiment if spectrum.getMSLevel() == 1])  
              
            selected_rt = st.slider("Select Retention Time (seconds)",   
                                   min_value=float(min_rt),   
                                   max_value=float(max_rt),  
                                   value=float(min_rt + (max_rt - min_rt) / 2))  
              
            # Find closest spectrum  
            closest_spectrum = None  
            min_diff = float('inf')  
              
            for spectrum in experiment:  
                if spectrum.getMSLevel() == 1:  
                    diff = abs(spectrum.getRT() - selected_rt)  
                    if diff < min_diff:  
                        min_diff = diff  
                        closest_spectrum = spectrum  
              
            if closest_spectrum:  
                mzs, intensities = closest_spectrum.get_peaks()  
                  
                # Create plot  
                fig = go.Figure()  
                fig.add_trace(go.Scatter(  
                    x=mzs,  
                    y=intensities,  
                    mode='lines',  
                    line=dict(color='#2563EB', width=1),  
                    name='Mass Spectrum'  
                ))  
                  
                fig.update_layout(  
                    title=f"Mass Spectrum at RT: {closest_spectrum.getRT():.2f} seconds",  
                    xaxis_title="m/z",  
                    yaxis_title="Intensity",  
                    template="plotly_white"  
                )  
                  
                st.plotly_chart(fig, use_container_width=True)  
                  
                # Store results  
                st.session_state.analysis_results = {  
                    "Analysis Type": "Mass Spectrum",  
                    "Retention Time": f"{closest_spectrum.getRT():.2f} seconds",  
                    "Number of Peaks": len(mzs),  
                    "Max Intensity": max(intensities) if intensities else 0,  
                    "m/z Range": f"{min(mzs) if mzs.size > 0 else 0} - {max(mzs) if mzs.size > 0 else 0}"  
                }  
                  
                # Store plot  
                st.session_state.plots = [fig]  
      
    elif page == "Report Generation":  
        st.header("Generate Report")  
          
        if st.session_state.experiment is None:  
            st.warning("Please upload data first.")  
            return  
          
        if not st.session_state.analysis_results:  
            st.warning("Please perform analysis first.")  
            return  
          
        # Report parameters  
        st.subheader("Report Parameters")  
          
        report_title = st.text_input("Report Title", "Mass Spectrometry Analysis Report")  
        report_description = st.text_area("Report Description", "Analysis of mass spectrometry data.")  
          
        if st.button("Generate PDF Report"):  
            # Generate PDF  
            pdf_bytes = generate_pdf_report(  
                report_title,  
                report_description,  
                st.session_state.analysis_results,  
                st.session_state.plots,  
                {"Analysis Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
            )  
              
            # Create download link  
            st.markdown(  
                get_pdf_download_link(pdf_bytes, f"{report_title.replace(' ', '_')}.pdf"),  
                unsafe_allow_html=True  
            )  
  
if __name__ == "__main__":  
    main()  
