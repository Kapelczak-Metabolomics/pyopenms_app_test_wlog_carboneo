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
  
# Create tabs for different functionalities    
tabs = st.tabs(["mzML Viewer", "MS2 Spectral Matching"])  
  
# -----------------------------------------------  
# Helper functions for processing mzML files  
# -----------------------------------------------  
  
def load_mzml_file(file_path):  
    exp = MSExperiment()  
    MzMLFile().load(file_path, exp)  
    return exp  
  
def extract_chromatogram(exp):  
    # Extract TIC from experiment by summing intensities  
    times = []  
    intensities = []  
    for spec in exp:  
        times.append(spec.getRT())  
        # Calculate TIC by summing all peak intensities  
        peaks = spec.get_peaks()  
        if len(peaks) > 0 and len(peaks[1]) > 0:  
            intensity = sum(peaks[1])  
        else:  
            intensity = 0  
        intensities.append(intensity)  
    return times, intensities  
  
def extract_eic(exp, target_mass, tolerance):  
    # Extract EIC for a specific target mass with tolerance  
    times = []  
    intensities = []  
    for spec in exp:  
        if spec.getMSLevel() == 1:  # MS1 level only  
            rt = spec.getRT()  
            peaks = spec.get_peaks()  
            if len(peaks) > 0 and len(peaks[0]) > 0:  
                mzs = peaks[0]  
                intens = peaks[1]  
                # Find peaks within tolerance of target mass  
                matches = [intens[i] for i, mz in enumerate(mzs) if abs(mz - target_mass) <= tolerance]  
                intensity = sum(matches) if matches else 0  
            else:  
                intensity = 0  
            times.append(rt)  
            intensities.append(intensity)  
    return times, intensities  
  
def extract_mass_spectra(exp, max_spectra=100):  
    # Extract mass spectra data for the first max_spectra spectra  
    data = []  
    for i, spec in enumerate(exp):  
        if i >= max_spectra:  
            break  
        rt = spec.getRT()  
        peaks = spec.get_peaks()  
        if len(peaks) > 0 and len(peaks[0]) > 0:  
            mzs = peaks[0]  
            intens = peaks[1]  
            for j in range(min(5, len(mzs))):  # Take up to 5 peaks per spectrum  
                data.append({  
                    "RT (s)": rt,  
                    "m/z": mzs[j],  
                    "Intensity": intens[j]  
                })  
    return pd.DataFrame(data)  
  
# -----------------------------------------------  
# Functions for PDF report generation  
# -----------------------------------------------  
  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, target_masses, tolerance, pdf_title="mzML Report", logo_path=None):  
    # Create a PDF report with TIC, EIC, and mass spectra data  
    pdf_buffer = io.BytesIO()  
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)  
      
    # Define styles  
    styles = getSampleStyleSheet()  
    styles.add(ParagraphStyle(  
        name='TitleStyle',  
        parent=styles['Title'],  
        fontName='Helvetica-Bold',  
        fontSize=16,  
        textColor=colors.HexColor("#171717"),  
        spaceAfter=12  
    ))  
    styles.add(ParagraphStyle(  
        name='HeaderStyle',  
        parent=styles['Heading2'],  
        fontName='Helvetica-Bold',  
        fontSize=14,  
        textColor=colors.HexColor("#171717"),  
        spaceAfter=6  
    ))  
    styles.add(ParagraphStyle(  
        name='NormalStyle',  
        parent=styles['Normal'],  
        fontName='Helvetica',  
        fontSize=10,  
        textColor=colors.HexColor("#171717"),  
        spaceAfter=6  
    ))  
      
    # Create content  
    flowables = []  
      
    # Add logo if provided  
    if logo_path:  
        img = Image.open(logo_path)  
        width, height = img.size  
        aspect_ratio = height / width  
        img_width = 2 * inch  # Set width to 2 inches  
        img_height = img_width * aspect_ratio  # Calculate height to maintain aspect ratio  
        logo = RLImage(logo_path, width=img_width, height=img_height)  
        flowables.append(logo)  
        flowables.append(Spacer(1, 12))  
      
    # Add title and metadata  
    flowables.append(Paragraph(pdf_title, styles['TitleStyle']))  
    flowables.append(Paragraph(f"File: {filename}", styles['NormalStyle']))  
    flowables.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['NormalStyle']))  
    flowables.append(Spacer(1, 12))  
      
    # Add TIC plot  
    tic_img_bytes = tic_fig.to_image(format="png")  
    with open("tic_temp.png", "wb") as f:  
        f.write(tic_img_bytes)  
    rl_tic = RLImage("tic_temp.png", width=6*inch, height=3*inch)  
    flowables.append(Paragraph("Total Ion Chromatogram (TIC)", styles["HeaderStyle"]))  
    flowables.append(rl_tic)  
    flowables.append(Spacer(1, 12))  
      
    # Add EIC plot  
    eic_img_bytes = eic_fig.to_image(format="png")  
    with open("eic_temp.png", "wb") as f:  
        f.write(eic_img_bytes)  
    rl_eic = RLImage("eic_temp.png", width=6*inch, height=3*inch)  
    masses_str = ", ".join([f"{m:.3f}" for m in target_masses])  
    flowables.append(Paragraph(f"Extracted Ion Chromatogram (EIC) for target masses: {masses_str} (±{tolerance})", styles["HeaderStyle"]))  
    flowables.append(rl_eic)  
    flowables.append(Spacer(1, 12))  
      
    # Add mass spectra table  
    flowables.append(Paragraph("Mass Spectra (sample)", styles["HeaderStyle"]))  
    sample_df = mass_df.head(10)  
    data = [sample_df.columns.to_list()] + sample_df.values.tolist()  
    table = Table(data)  
    table.setStyle(TableStyle([  
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),  
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),  
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)  
    ]))  
    flowables.append(table)  
      
    doc.build(flowables)  
    pdf_buffer.seek(0)  
    return pdf_buffer  
  
def get_download_link(pdf_buffer, base_filename):  
    b64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')  
    download_link = f'<a class="download-button" href="data:application/pdf;base64,{b64_pdf}" download="{base_filename}_report.pdf">Download PDF Report</a>'  
    return download_link  
  
# -----------------------------------------------  
# mzML Viewer Tab  
# -----------------------------------------------  
with tabs[0]:  
    st.header("mzML Viewer")  
    st.markdown("Upload an mzML file to view its chromatogram, extract ions based on target masses, and generate a PDF report.")  
    uploaded_file = st.file_uploader("Upload mzML File", type=["mzML"])  
      
    if uploaded_file is not None:  
        try:  
            # Save uploaded file temporarily  
            temp_file_path = "temp_upload.mzML"  
            with open(temp_file_path, "wb") as f:  
                f.write(uploaded_file.getbuffer())  
              
            # Load mzML file and extract data  
            exp = load_mzml_file(temp_file_path)  
            times, intensities = extract_chromatogram(exp)  
            mass_df = extract_mass_spectra(exp)  
              
            # Plot TIC using Plotly  
            tic_fig = go.Figure()  
            tic_fig.add_trace(go.Scatter(x=times, y=intensities, mode='lines', line=dict(color="#2563EB")))  
            tic_fig.update_layout(  
                title="Total Ion Chromatogram (TIC)",  
                xaxis_title="Retention Time (s)",  
                yaxis_title="Intensity",  
                plot_bgcolor="#FFFFFF",  
                paper_bgcolor="#FFFFFF"  
            )  
            st.plotly_chart(tic_fig)  
              
            # Display mass spectra data  
            st.dataframe(mass_df.head(10))  
              
            # Input for target masses (multiple, comma-separated)  
            target_mass_input = st.text_input("Enter target mass values (comma-separated)", "500.0, 600.0")  
            tolerance = st.number_input("Mass Tolerance (±)", value=0.5, min_value=0.01, max_value=10.0)  
              
            # Parse target masses  
            try:  
                target_masses = [float(mass.strip()) for mass in target_mass_input.split(",")]  
                  
                # Plot EIC for each target mass  
                eic_fig = go.Figure()  
                colors = ["#2563EB", "#24EB84", "#B2EB24", "#EB3424", "#D324EB"]  # Color palette  
                  
                for i, mass in enumerate(target_masses):  
                    eic_times, eic_intensities = extract_eic(exp, mass, tolerance)  
                    color_idx = i % len(colors)  
                    eic_fig.add_trace(go.Scatter(  
                        x=eic_times,   
                        y=eic_intensities,   
                        mode='lines',   
                        name=f"m/z {mass:.3f}",  
                        line=dict(color=colors[color_idx])  
                    ))  
                  
                eic_fig.update_layout(  
                    title="Extracted Ion Chromatogram (EIC)",  
                    xaxis_title="Retention Time (s)",  
                    yaxis_title="Intensity",  
                    plot_bgcolor="#FFFFFF",  
                    paper_bgcolor="#FFFFFF",  
                    legend=dict(  
                        orientation="h",  
                        yanchor="bottom",  
                        y=1.02,  
                        xanchor="right",  
                        x=1  
                    )  
                )  
                st.plotly_chart(eic_fig)  
                  
                # PDF Report Generation  
                st.markdown("### PDF Report")  
                if st.button("Generate PDF Report"):  
                    with st.spinner("Generating PDF report..."):  
                        logo_path = "temp_logo.png" if logo_file is not None else None  
                          
                        pdf_buffer = create_pdf_report(  
                            filename=uploaded_file.name,  
                            tic_fig=tic_fig,  
                            eic_fig=eic_fig,  
                            mass_df=mass_df,  
                            target_masses=target_masses,  
                            tolerance=tolerance,  
                            pdf_title=pdf_title_input,  
                            logo_path=logo_path  
                        )  
                          
                        download_link = get_download_link(pdf_buffer, uploaded_file.name.split('.')[0])  
                        st.markdown(download_link, unsafe_allow_html=True)  
                          
                        # Add some CSS to style the download button  
                        st.markdown("""  
                        <style>  
                        .download-button {  
                            display: inline-block;  
                            padding: 0.5em 1em;  
                            background-color: #2563EB;  
                            color: white;  
                            text-decoration: none;  
                            border-radius: 4px;  
                            font-weight: bold;  
                            margin-top: 1em;  
                        }  
                        .download-button:hover {  
                            background-color: #1E40AF;  
                        }  
                        </style>  
                        """, unsafe_allow_html=True)  
                  
            except ValueError as e:  
                st.error(f"Error parsing mass values: {str(e)}")  
                st.info("Please enter valid numeric values separated by commas.")  
                  
        except Exception as e:  
            st.error(f"Error processing mzML file: {str(e)}")  
            st.info("Please ensure the file is a valid mzML format.")  
  
# -----------------------------------------------  
# MS2 Spectral Matching Tab  
# -----------------------------------------------  
with tabs[1]:  
    st.header("MS2 Spectral Matching")  
    st.markdown("This tab demonstrates MS2 spectral matching functionality.")  
      
    # Simple dummy implementation for demonstration  
    query_input = st.text_input("Enter spectral intensities (comma-separated)", "100,200,150")  
      
    if query_input:  
        try:  
            query_intensities = [float(x.strip()) for x in query_input.split(",")]  
              
            # Dummy spectral matching (for demonstration)  
            library_spectra = [  
                ('Spectrum_A', np.random.uniform(0.8, 1.0)),  
                ('Spectrum_B', np.random.uniform(0.5, 0.8)),  
                ('Spectrum_C', np.random.uniform(0.2, 0.5)),  
                ('Spectrum_D', np.random.uniform(0.1, 0.4)),  
                ('Spectrum_E', np.random.uniform(0.3, 0.7))  
            ]  
              
            # Sort by similarity score (descending)  
            results = sorted(library_spectra, key=lambda x: x[1], reverse=True)  
              
            st.markdown("### Matching Results")  
            if results:  
                # Create a DataFrame for results  
                results_df = pd.DataFrame(results, columns=["Spectrum Name", "Similarity Score"])  
                results_df["Similarity Score"] = results_df["Similarity Score"].apply(lambda x: round(x, 3))  
                  
                # Display results as a table  
                st.dataframe(results_df)  
                  
                # Plot top 5 matches  
                st.markdown("### Top Matches Visualization")  
                top_results = results[:5] if len(results) >= 5 else results  
                  
                fig = go.Figure()  
                for name, score in top_results:  
                    fig.add_trace(go.Bar(  
                        x=[name],  
                        y=[score],  
                        name=name  
                    ))  
                  
                fig.update_layout(  
                    title="Top Spectral Matches",  
                    xaxis_title="Spectrum Name",  
                    yaxis_title="Similarity Score",  
                    plot_bgcolor="#FFFFFF",  
                    paper_bgcolor="#FFFFFF"  
                )  
                st.plotly_chart(fig)  
            else:  
                st.write("No matching spectra found.")  
        except Exception as e:  
            st.error(f"Error processing your query: {str(e)}")  
