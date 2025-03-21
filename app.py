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
    # Extract TIC from experiment  
    times = []  
    intensities = []  
    for spec in exp:  
        times.append(spec.getRT())  
        intensities.append(spec.getTIC())  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Extract mass spectra data  
    masses = []  
    intensities = []  
    rts = []  
    for spec in exp:  
        rt = spec.getRT()  
        for mz, intensity in zip(spec.get_peaks()[0], spec.get_peaks()[1]):  
            masses.append(mz)  
            intensities.append(intensity)  
            rts.append(rt)  
    mass_df = pd.DataFrame({  
        'RT': rts,  
        'm/z': masses,  
        'Intensity': intensities  
    })  
    return mass_df  
  
def extract_eic(exp, target_mass, tolerance):  
    # Extract EIC for a specific mass  
    times = []  
    intensities = []  
    for spec in exp:  
        rt = spec.getRT()  
        mzs, ints = spec.get_peaks()  
        intensity = 0  
        for mz, inten in zip(mzs, ints):  
            if abs(mz - target_mass) <= tolerance:  
                intensity += inten  
        times.append(rt)  
        intensities.append(intensity)  
    return times, intensities  
  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, target_mass, tolerance, pdf_title):  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter)  
    styles = getSampleStyleSheet()  
      
    # Create custom styles  
    title_style = ParagraphStyle(  
        'Title',  
        parent=styles['Heading1'],  
        fontSize=24,  
        alignment=TA_CENTER,  
        spaceAfter=20  
    )  
      
    subtitle_style = ParagraphStyle(  
        'Subtitle',  
        parent=styles['Heading2'],  
        fontSize=18,  
        alignment=TA_LEFT,  
        spaceAfter=10  
    )  
      
    normal_style = ParagraphStyle(  
        'Normal',  
        parent=styles['Normal'],  
        fontSize=12,  
        spaceAfter=6  
    )  
      
    # Create content elements  
    elements = []  
      
    # Add title  
    elements.append(Paragraph(pdf_title, title_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add file information  
    elements.append(Paragraph("File Information", subtitle_style))  
    elements.append(Paragraph(f"Filename: {filename}", normal_style))  
    elements.append(Paragraph(f"Date Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add logo if available  
    if os.path.exists("temp_logo.png"):  
        img = RLImage("temp_logo.png", width=2*inch, height=1*inch)  
        elements.append(img)  
        elements.append(Spacer(1, 0.25*inch))  
      
    # Add TIC plot  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", subtitle_style))  
    if kaleido_available:  
        tic_img_path = "tic_plot.png"  
        tic_fig.write_image(tic_img_path)  
        elements.append(RLImage(tic_img_path, width=6*inch, height=4*inch))  
    else:  
        elements.append(Paragraph("Kaleido package not available for image export.", normal_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add EIC plot  
    elements.append(Paragraph(f"Extracted Ion Chromatogram (EIC) for m/z {target_mass} ± {tolerance}", subtitle_style))  
    if kaleido_available:  
        eic_img_path = "eic_plot.png"  
        eic_fig.write_image(eic_img_path)  
        elements.append(RLImage(eic_img_path, width=6*inch, height=4*inch))  
    else:  
        elements.append(Paragraph("Kaleido package not available for image export.", normal_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add mass spectra data table  
    elements.append(Paragraph("Mass Spectra Data (Top 10 Intensities)", subtitle_style))  
      
    # Sort by intensity and get top 10  
    top_mass_df = mass_df.sort_values('Intensity', ascending=False).head(10)  
      
    # Create table data  
    table_data = [['RT (s)', 'm/z', 'Intensity']]  
    for _, row in top_mass_df.iterrows():  
        table_data.append([f"{row['RT']:.2f}", f"{row['m/z']:.4f}", f"{row['Intensity']:.0f}"])  
      
    # Create table  
    table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch])  
    table.setStyle(TableStyle([  
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),  
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  
        ('GRID', (0, 0), (-1, -1), 1, colors.black)  
    ]))  
    elements.append(table)  
      
    # Build PDF  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
def get_download_link(buffer, filename):  
    b64 = base64.b64encode(buffer.read()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" class="download-button" download="{filename}_report.pdf">Download PDF Report</a>'  
    return href  
  
# Basic cosine similarity function for spectral matching  
def cosine_similarity(a, b):  
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)  
  
def ms2_matching(query_intensities, library_spectra):  
    results = []  
    for spec_name, spec_intensities in library_spectra.items():  
        # Ensure both arrays are the same length for comparison  
        min_len = min(len(query_intensities), len(spec_intensities))  
        query_intensities_trimmed = query_intensities[:min_len]  
        spec_intensities_trimmed = spec_intensities[:min_len]  
          
        # If lengths are different, pad with zeros  
        if len(query_intensities_trimmed) < len(spec_intensities_trimmed):  
            query_intensities_trimmed = np.pad(query_intensities_trimmed,   
                                              (0, len(spec_intensities_trimmed) - len(query_intensities_trimmed)))  
        elif len(spec_intensities_trimmed) < len(query_intensities_trimmed):  
            spec_intensities_trimmed = np.pad(spec_intensities_trimmed,  
                                             (0, len(query_intensities_trimmed) - len(spec_intensities_trimmed)))  
          
        sim = cosine_similarity(np.array(query_intensities_trimmed), np.array(spec_intensities_trimmed))  
        results.append((spec_name, sim))  
    results.sort(key=lambda x: x[1], reverse=True)  
    return results  
  
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
  
# mzML Viewer Tab  
with tabs[0]:  
    st.markdown("Upload an mzML file to view its corresponding chromatogram, mass spectra data, and generate a modern PDF report.")  
      
    # File uploader for mzML files  
    uploaded_file = st.file_uploader("Upload mzML File", type=["mzML"])  
      
    if uploaded_file is not None:  
        # Save the uploaded file to a temporary location  
        with open("temp.mzML", "wb") as f:  
            f.write(uploaded_file.getbuffer())  
          
        try:  
            # Load the mzML file  
            exp = load_mzml_file("temp.mzML")  
            st.success(f"File '{uploaded_file.name}' loaded successfully!")  
              
            # Extract and display TIC  
            st.markdown("### Total Ion Chromatogram (TIC)")  
            times, intensities = extract_chromatogram(exp)  
              
            # Create TIC plot  
            tic_fig = go.Figure()  
            tic_fig.add_trace(go.Scatter(  
                x=times,  
                y=intensities,  
                mode='lines',  
                line=dict(color='#2563EB', width=2),  
                name='TIC'  
            ))  
            tic_fig.update_layout(  
                title="Total Ion Chromatogram",  
                xaxis_title="Retention Time (s)",  
                yaxis_title="Intensity",  
                plot_bgcolor="#FFFFFF",  
                paper_bgcolor="#FFFFFF"  
            )  
            st.plotly_chart(tic_fig)  
              
            # Extract and display mass spectra data  
            st.markdown("### Mass Spectra Data")  
            mass_df = extract_mass_spectra(exp)  
            st.dataframe(mass_df.head(10))  
              
            # EIC extraction  
            st.markdown("### Extracted Ion Chromatogram (EIC)")  
            target_mass = st.number_input("Target m/z", value=500.0)  
            tolerance = st.number_input("Tolerance (±)", value=0.5)  
              
            # Extract and display EIC  
            eic_times, eic_intensities = extract_eic(exp, target_mass, tolerance)  
              
            # Create EIC plot  
            eic_fig = go.Figure()  
            eic_fig.add_trace(go.Scatter(  
                x=eic_times,  
                y=eic_intensities,  
                mode='lines',  
                line=dict(color='#24EB84', width=2),  
                name=f'EIC m/z {target_mass} ± {tolerance}'  
            ))  
            eic_fig.update_layout(  
                title=f"Extracted Ion Chromatogram for m/z {target_mass} ± {tolerance}",  
                xaxis_title="Retention Time (s)",  
                yaxis_title="Intensity",  
                plot_bgcolor="#FFFFFF",  
                paper_bgcolor="#FFFFFF"  
            )  
            st.plotly_chart(eic_fig)  
              
            # PDF Report Generation  
            st.markdown("### PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    # Create PDF report  
                    pdf_buffer = create_pdf_report(  
                        filename=uploaded_file.name,  
                        tic_fig=tic_fig,  
                        eic_fig=eic_fig,  
                        mass_df=mass_df.head(10),  
                        target_mass=target_mass,  
                        tolerance=tolerance,  
                        pdf_title=pdf_title_input  
                    )  
                      
                    # Create download link  
                    download_link = get_download_link(pdf_buffer, uploaded_file.name.split('.')[0])  
                      
                    # Display download link with custom styling  
                    st.markdown('''  
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
                    ''', unsafe_allow_html=True)  
                      
                    st.markdown(download_link, unsafe_allow_html=True)  
                    st.success("PDF report generated successfully! Click the button above to download.")  
        except Exception as e:  
            st.error("Error processing mzML file: " + str(e))  
    else:  
        st.info("Please upload an mzML file to begin.")  
  
# MS2 Spectral Matching Tab (New functionality)  
with tabs[1]:  
    st.header("MS2 Spectral Matching")  
    st.markdown("Upload your MS2 library as a CSV file for spectral matching. The CSV file should have the following columns:")  
    st.markdown("- **Spectrum Name**: Identifier for the spectrum")  
    st.markdown("- **m/z values**: Comma-separated m/z values (not used in this example)")  
    st.markdown("- **intensity values**: Comma-separated intensity values")  
      
    uploaded_library = st.file_uploader("Upload Library CSV", type=["csv"], key="library")  
    library_spectra = {}  
    if uploaded_library is not None:  
        try:  
            library_df = pd.read_csv(uploaded_library)  
            st.success("Library uploaded successfully!")  
            st.dataframe(library_df.head())  
            error_rows = 0  
            for idx, row in library_df.iterrows():  
                try:  
                    int_str = row['intensity values']  
                    intensity_values = [float(x.strip()) for x in int_str.split(",")]  
                    library_spectra[row['Spectrum Name']] = intensity_values  
                except Exception as e:  
                    error_rows += 1  
                    st.warning("Error parsing row " + str(idx) + ": " + str(e))  
            if error_rows:  
                st.info("Parsed library with " + str(error_rows) + " row(s) skipped due to errors.")  
        except Exception as e:  
            st.error("Error reading library CSV: " + str(e))  
      
    st.markdown("### Query Spectrum Input")  
    st.markdown("Enter your query spectrum intensity values as comma-separated numbers:")  
    query_input = st.text_input("Query Spectrum Intensities", key="query")  
      
    if st.button("Perform Matching"):  
        if query_input.strip() == "":  
            st.error("Please provide query spectrum intensities.")  
        elif not library_spectra:  
            st.error("Please upload a valid library CSV before matching.")  
        else:  
            try:  
                query_intensities = [float(x.strip()) for x in query_input.split(",")]  
                results = ms2_matching(query_intensities, library_spectra)  
                  
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
                st.error("Error processing your query: " + str(e))  
