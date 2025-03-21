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
  
def extract_eic(exp, target_mass, tolerance):  
    # Extract EIC for a specific mass  
    times = []  
    intensities = []  
    for spec in exp:  
        rt = spec.getRT()  
        mzs, ints = spec.get_peaks()  
        intensity = 0  
        for i in range(len(mzs)):  
            if abs(mzs[i] - target_mass) <= tolerance:  
                intensity += ints[i]  
        times.append(rt)  
        intensities.append(intensity)  
    return times, intensities  
  
def extract_mass_spectra(exp):  
    # Extract mass spectra data (first 1000 peaks for demonstration)  
    data = []  
    count = 0  
    for spec in exp:  
        rt = spec.getRT()  
        mzs, ints = spec.get_peaks()  
        for i in range(min(len(mzs), 20)):  # Limit to 20 peaks per spectrum  
            data.append({  
                "RT": rt,  
                "m/z": mzs[i],  
                "Intensity": ints[i]  
            })  
            count += 1  
            if count >= 1000:  # Limit to 1000 total peaks  
                break  
        if count >= 1000:  
            break  
    return pd.DataFrame(data)  
  
def create_pdf_report(filename, tic_fig, eic_fig, mass_df, target_masses, tolerance, pdf_title, logo_path=None):  
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)  
      
    # Define styles  
    styles = getSampleStyleSheet()  
      
    # Create custom styles for modern look  
    title_style = ParagraphStyle(  
        'CustomTitle',  
        parent=styles['Title'],  
        fontSize=24,  
        fontName='Helvetica-Bold',  
        spaceAfter=12,  
        textColor=colors.HexColor("#2563EB")  
    )  
      
    heading_style = ParagraphStyle(  
        'CustomHeading',  
        parent=styles['Heading1'],  
        fontSize=18,  
        fontName='Helvetica-Bold',  
        spaceAfter=10,  
        textColor=colors.HexColor("#171717")  
    )  
      
    subheading_style = ParagraphStyle(  
        'CustomSubheading',  
        parent=styles['Heading2'],  
        fontSize=14,  
        fontName='Helvetica-Bold',  
        spaceAfter=8,  
        textColor=colors.HexColor("#4B5563")  
    )  
      
    normal_style = ParagraphStyle(  
        'CustomNormal',  
        parent=styles['Normal'],  
        fontSize=12,  
        fontName='Helvetica',  
        spaceAfter=6,  
        textColor=colors.HexColor("#374151")  
    )  
      
    # Create content elements  
    elements = []  
      
    # Add logo if provided  
    if logo_path is not None:  
        img = Image.open(logo_path)  
        width, height = img.size  
        aspect_ratio = width / height  
          
        # Set max width to 2 inches, calculate height based on aspect ratio  
        img_width = 2 * inch  
        img_height = img_width / aspect_ratio  
          
        logo = RLImage(logo_path, width=img_width, height=img_height)  
        elements.append(logo)  
        elements.append(Spacer(1, 0.25 * inch))  
      
    # Add title  
    elements.append(Paragraph(pdf_title, title_style))  
    elements.append(Spacer(1, 0.25 * inch))  
      
    # Add file info  
    elements.append(Paragraph("File Information", heading_style))  
    elements.append(Paragraph(f"Filename: {filename}", normal_style))  
    elements.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))  
    elements.append(Spacer(1, 0.25 * inch))  
      
    # Add TIC plot  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", heading_style))  
      
    # Save TIC figure to temporary file  
    if kaleido_available:  
        tic_img_path = "temp_tic.png"  
        tic_fig.write_image(tic_img_path, scale=2)  
        tic_img = RLImage(tic_img_path, width=6*inch, height=4*inch)  
        elements.append(tic_img)  
    else:  
        elements.append(Paragraph("TIC plot image export requires kaleido package.", normal_style))  
      
    elements.append(Spacer(1, 0.25 * inch))  
      
    # Add EIC plot  
    mass_str = ", ".join([str(m) for m in target_masses])  
    elements.append(Paragraph(f"Extracted Ion Chromatogram (m/z: {mass_str}, tolerance: ±{tolerance})", heading_style))  
      
    # Save EIC figure to temporary file  
    if kaleido_available:  
        eic_img_path = "temp_eic.png"  
        eic_fig.write_image(eic_img_path, scale=2)  
        eic_img = RLImage(eic_img_path, width=6*inch, height=4*inch)  
        elements.append(eic_img)  
    else:  
        elements.append(Paragraph("EIC plot image export requires kaleido package.", normal_style))  
      
    elements.append(Spacer(1, 0.25 * inch))  
      
    # Add mass spectra data  
    elements.append(Paragraph("Mass Spectra Data (Sample)", heading_style))  
      
    # Convert dataframe to table  
    data = [["RT", "m/z", "Intensity"]]  
    for i, row in mass_df.head(10).iterrows():  
        data.append([f"{row['RT']:.2f}", f"{row['m/z']:.4f}", f"{row['Intensity']:.0f}"])  
      
    # Create table  
    table = Table(data, colWidths=[1.5*inch, 2*inch, 2*inch])  
    table.setStyle(TableStyle([  
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),  
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#171717")),  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('FONTSIZE', (0, 0), (-1, 0), 12),  
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),  
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),  
    ]))  
      
    elements.append(table)  
      
    # Build PDF  
    doc.build(elements)  
    buffer.seek(0)  
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
              
            st.dataframe(mass_df.head(10))  
              
            # Multiple target masses input  
            st.subheader("Extract Ion Chromatograms")  
            target_masses_input = st.text_input("Target Masses (comma-separated)", "500.0, 600.0")  
            tolerance = st.number_input("Mass Tolerance (±)", value=0.5)  
              
            # Parse target masses  
            try:  
                target_masses = [float(mass.strip()) for mass in target_masses_input.split(",")]  
                  
                # Extract EICs for each target mass  
                eic_fig = go.Figure()  
                  
                # Color palette for multiple traces  
                colors = ["#2563EB", "#24EB84", "#B2EB24", "#EB3424", "#D324EB"]  
                  
                for i, mass in enumerate(target_masses):  
                    eic_times, eic_intensities = extract_eic(exp, mass, tolerance)  
                    color_idx = i % len(colors)  
                    eic_fig.add_trace(go.Scatter(  
                        x=eic_times,   
                        y=eic_intensities,   
                        mode='lines',   
                        name=f"m/z {mass}",  
                        line=dict(color=colors[color_idx])  
                    ))  
                  
                eic_fig.update_layout(  
                    title=f"Extracted Ion Chromatogram(s)",  
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
              
            except ValueError as e:  
                st.error(f"Error parsing masses: {str(e)}")  
                eic_fig = go.Figure()  # Empty figure for PDF generation  
              
            st.markdown("### PDF Report")  
            if st.button("Generate PDF Report"):  
                with st.spinner("Generating PDF report..."):  
                    logo_path = None  
                    if logo_file is not None:  
                        logo_path = "temp_logo.png"  
                      
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
            st.error(f"Error processing mzML file: {str(e)}")  
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
        # Ensure vectors are of equal length by padding with zeros  
        max_len = max(len(a), len(b))  
        a_padded = np.pad(a, (0, max_len - len(a)), 'constant')  
        b_padded = np.pad(b, (0, max_len - len(b)), 'constant')  
          
        return np.dot(a_padded, b_padded) / (np.linalg.norm(a_padded) * np.linalg.norm(b_padded) + 1e-10)  
      
    def ms2_matching(query_intensities, library_spectra):  
        results = []  
        for spec_name, spec_intensities in library_spectra.items():  
            sim = cosine_similarity(np.array(query_intensities), np.array(spec_intensities))  
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
