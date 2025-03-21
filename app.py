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
            total_intensity = sum(peaks[1])  
        else:  
            total_intensity = 0  
        intensities.append(total_intensity)  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Extract mass spectra data  
    data = []  
    for i, spec in enumerate(exp):  
        if i > 100:  # Limit to first 100 spectra for performance  
            break  
        rt = spec.getRT()  
        peaks = spec.get_peaks()  
        if len(peaks[0]) > 0:  
            for mz, intensity in zip(peaks[0], peaks[1]):  
                if intensity > 0:  # Only include peaks with intensity  
                    data.append({  
                        "RT (s)": rt,  
                        "m/z": mz,  
                        "Intensity": intensity  
                    })  
      
    # Create DataFrame  
    if data:  
        mass_df = pd.DataFrame(data)  
        return mass_df  
    else:  
        # Return empty DataFrame with correct columns if no data  
        return pd.DataFrame(columns=["RT (s)", "m/z", "Intensity"])  
  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, target_mass, tolerance, pdf_title, logo_path=None):  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)  
      
    # Define styles  
    styles = getSampleStyleSheet()  
      
    # Create modern styles  
    title_style = ParagraphStyle(  
        'ModernTitle',  
        parent=styles['Heading1'],  
        fontSize=24,  
        fontName='Helvetica-Bold',  
        textColor=colors.HexColor('#2563EB'),  
        spaceAfter=20,  
        alignment=TA_CENTER  
    )  
      
    subtitle_style = ParagraphStyle(  
        'ModernSubtitle',  
        parent=styles['Heading2'],  
        fontSize=18,  
        fontName='Helvetica-Bold',  
        textColor=colors.HexColor('#333333'),  
        spaceAfter=12,  
        spaceBefore=12  
    )  
      
    normal_style = ParagraphStyle(  
        'ModernNormal',  
        parent=styles['Normal'],  
        fontSize=12,  
        fontName='Helvetica',  
        textColor=colors.HexColor('#444444'),  
        spaceAfter=8  
    )  
      
    info_style = ParagraphStyle(  
        'ModernInfo',  
        parent=styles['Normal'],  
        fontSize=10,  
        fontName='Helvetica',  
        textColor=colors.HexColor('#666666'),  
        spaceAfter=4  
    )  
      
    # Create content elements  
    elements = []  
      
    # Add logo if provided (with preserved aspect ratio)  
    if logo_path and os.path.exists(logo_path):  
        try:  
            img = Image.open(logo_path)  
            width, height = img.size  
            aspect_ratio = height / width  
              
            # Set max width to 2 inches, calculate height based on aspect ratio  
            max_width = 2 * inch  
            img_width = min(max_width, width)  
            img_height = img_width * aspect_ratio  
              
            logo = RLImage(logo_path, width=img_width, height=img_height)  
            elements.append(logo)  
            elements.append(Spacer(1, 0.25 * inch))  
        except Exception as e:  
            # If there's an error with the logo, just continue without it  
            pass  
      
    # Add title  
    elements.append(Paragraph(pdf_title, title_style))  
    elements.append(Spacer(1, 0.25 * inch))  
      
    # Add file info  
    elements.append(Paragraph(f"File: {filename}", info_style))  
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", info_style))  
    elements.append(Spacer(1, 0.5 * inch))  
      
    # Add TIC plot  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", subtitle_style))  
      
    if kaleido_available:  
        tic_img_path = "tic_plot.png"  
        tic_fig.write_image(tic_img_path, scale=2)  
        elements.append(RLImage(tic_img_path, width=6*inch, height=3*inch))  
    else:  
        elements.append(Paragraph("Plot image export not available. Install kaleido package.", normal_style))  
      
    elements.append(Spacer(1, 0.5 * inch))  
      
    # Add EIC plot  
    elements.append(Paragraph(f"Extracted Ion Chromatogram (EIC) for m/z {target_mass} ± {tolerance}", subtitle_style))  
      
    if kaleido_available:  
        eic_img_path = "eic_plot.png"  
        eic_fig.write_image(eic_img_path, scale=2)  
        elements.append(RLImage(eic_img_path, width=6*inch, height=3*inch))  
    else:  
        elements.append(Paragraph("Plot image export not available. Install kaleido package.", normal_style))  
      
    elements.append(Spacer(1, 0.5 * inch))  
      
    # Add mass spectra data table  
    elements.append(Paragraph("Mass Spectra Data (Top 10 Peaks)", subtitle_style))  
      
    # Sort by intensity and get top 10  
    if not mass_df.empty:  
        top_peaks = mass_df.sort_values(by="Intensity", ascending=False).head(10)  
          
        # Format the data for the table  
        data = [["RT (s)", "m/z", "Intensity"]]  
        for _, row in top_peaks.iterrows():  
            data.append([  
                f"{row['RT (s)']:.2f}",  
                f"{row['m/z']:.4f}",  
                f"{row['Intensity']:.0f}"  
            ])  
          
        # Create table  
        table = Table(data, colWidths=[1.5*inch, 2*inch, 2*inch])  
        table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('FONTSIZE', (0, 0), (-1, 0), 12),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),  
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),  
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),  
            ('FONTSIZE', (0, 1), (-1, -1), 10),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white])  
        ]))  
          
        elements.append(table)  
    else:  
        elements.append(Paragraph("No mass spectra data available.", normal_style))  
      
    # Build PDF  
    doc.build(elements)  
    buffer.seek(0)  
      
    # Clean up temporary files  
    if kaleido_available:  
        if os.path.exists("tic_plot.png"):  
            os.remove("tic_plot.png")  
        if os.path.exists("eic_plot.png"):  
            os.remove("eic_plot.png")  
      
    return buffer  
  
def get_download_link(pdf_buffer, base_filename):  
    pdf_buffer.seek(0)  
    b64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')  
    href = f'<a class="download-button" href="data:application/pdf;base64,{b64_pdf}" download="{base_filename}_report.pdf">Download PDF Report</a>'  
    return href  
  
# -----------------------------------------------    
# mzML Viewer Tab    
# -----------------------------------------------    
with tabs[0]:  
    st.header("mzML Viewer")  
    st.markdown("Upload an mzML file to view its corresponding chromatogram, mass spectra data, and generate a PDF report.")  
    uploaded_file = st.file_uploader("Upload mzML File", type=["mzML"])  
      
    if uploaded_file is not None:  
        try:  
            # Save the uploaded file to a temporary file for processing  
            temp_file_path = "temp_upload.mzML"  
            with open(temp_file_path, "wb") as f:  
                f.write(uploaded_file.getbuffer())  
              
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
              
            # Dummy EIC plot (for demonstration)    
            eic_fig = go.Figure()  
            eic_fig.add_trace(go.Scatter(x=times, y=[i*0.5 for i in intensities], mode='lines', line=dict(color="#24EB84")))  
            eic_fig.update_layout(  
                title="Extracted Ion Chromatogram (EIC)",  
                xaxis_title="Retention Time (s)",  
                yaxis_title="Intensity",  
                plot_bgcolor="#FFFFFF",  
                paper_bgcolor="#FFFFFF"  
            )  
            st.plotly_chart(eic_fig)  
              
            st.dataframe(mass_df.head(10))  
              
            target_mass = st.number_input("Target Mass", value=500.0)  
            tolerance = st.number_input("Tolerance", value=0.5)  
              
            st.markdown("### PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    logo_path = None  
                    if logo_file is not None:  
                        logo_path = "temp_logo.png"  
                      
                    pdf_buffer = create_pdf_report(filename=uploaded_file.name,  
                                                   tic_fig=tic_fig,  
                                                   eic_fig=eic_fig,  
                                                   mass_df=mass_df,  
                                                   target_mass=target_mass,  
                                                   tolerance=tolerance,  
                                                   pdf_title=pdf_title_input,  
                                                   logo_path=logo_path)  
                    download_link = get_download_link(pdf_buffer, uploaded_file.name.split('.')[0])  
                      
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
  
# -----------------------------------------------  
# MS2 Spectral Matching Tab  
# -----------------------------------------------  
with tabs[1]:  
    st.header("MS2 Spectral Matching")  
    st.markdown("Upload your MS2 library as a CSV file for spectral matching.")  
    st.markdown("The CSV file should have the following columns:")  
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
                    st.warning(f"Error parsing row {idx}: {str(e)}")  
            if error_rows:  
                st.info(f"Parsed library with {error_rows} row(s) skipped due to errors.")  
        except Exception as e:  
            st.error(f"Error reading library CSV: {str(e)}")  
      
    st.markdown("### Query Spectrum Input")  
    st.markdown("Enter your query spectrum intensity values as comma-separated numbers:")  
    query_input = st.text_input("Query Spectrum Intensities", key="query")  
      
    # Basic cosine similarity function for spectral matching  
    def cosine_similarity(a, b):  
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)  
      
    def ms2_matching(query_intensities, library_spectra):  
        results = []  
        for spec_name, spec_intensities in library_spectra.items():  
            # Make sure vectors are the same length for comparison  
            max_len = max(len(query_intensities), len(spec_intensities))  
            query_padded = query_intensities + [0] * (max_len - len(query_intensities))  
            spec_padded = spec_intensities + [0] * (max_len - len(spec_intensities))  
              
            sim = cosine_similarity(np.array(query_padded), np.array(spec_padded))  
            results.append((spec_name, sim))  
        results.sort(key=lambda x: x[1], reverse=True)  
        return results  
      
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
                st.error(f"Error processing your query: {str(e)}")  
