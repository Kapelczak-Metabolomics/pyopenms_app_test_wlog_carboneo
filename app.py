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
    # Extract TIC (Total Ion Chromatogram)  
    times = []  
    intensities = []  
    for spec in exp:  
        if spec.getMSLevel() == 1:  # MS1 level  
            times.append(spec.getRT())  
            intensities.append(sum(spec.get_peaks()[1]))  
    return times, intensities  
  
def extract_eic(exp, target_mass, tolerance=0.5):  
    # Extract EIC (Extracted Ion Chromatogram) for a specific m/z value  
    times = []  
    intensities = []  
    for spec in exp:  
        if spec.getMSLevel() == 1:  # MS1 level  
            rt = spec.getRT()  
            mzs, ints = spec.get_peaks()  
            # Find intensities within the mass tolerance  
            for i, mz in enumerate(mzs):  
                if abs(mz - target_mass) <= tolerance:  
                    times.append(rt)  
                    intensities.append(ints[i])  
                    break  
            else:  
                # No matching peak found, add zero intensity  
                times.append(rt)  
                intensities.append(0)  
    return times, intensities  
  
def extract_mass_spectra(exp, max_spectra=100):  
    # Extract mass spectra data for the first max_spectra MS1 spectra  
    data = []  
    count = 0  
    for spec in exp:  
        if spec.getMSLevel() == 1 and count < max_spectra:  # MS1 level  
            rt = spec.getRT()  
            mzs, ints = spec.get_peaks()  
            # Take top 5 peaks  
            if len(mzs) > 0:  
                sorted_indices = np.argsort(ints)[-5:]  
                for idx in sorted_indices:  
                    data.append({  
                        "RT (s)": round(rt, 2),  
                        "m/z": round(mzs[idx], 4),  
                        "Intensity": int(ints[idx])  
                    })  
                count += 1  
    return pd.DataFrame(data)  
  
def create_pdf_report(tic_fig, eic_fig, mass_df, target_masses, tolerance, title="mzML Report"):  
    # Create a PDF report with the chromatogram and mass spectra data  
    pdf_buffer = io.BytesIO()  
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, title=title)  
      
    # Create styles  
    styles = getSampleStyleSheet()  
    styles.add(ParagraphStyle(  
        name='HeaderStyle',  
        parent=styles['Heading2'],  
        fontName='Helvetica-Bold',  
        fontSize=14,  
        textColor=colors.HexColor("#2563EB"),  
        spaceAfter=12  
    ))  
    styles.add(ParagraphStyle(  
        name='NormalStyle',  
        parent=styles['Normal'],  
        fontName='Helvetica',  
        fontSize=10,  
        textColor=colors.HexColor("#171717"),  
        spaceAfter=6  
    ))  
      
    # Create flowables (content elements)  
    flowables = []  
      
    # Add title and date  
    title_style = ParagraphStyle(  
        name='TitleStyle',  
        parent=styles['Heading1'],  
        fontName='Helvetica-Bold',  
        fontSize=18,  
        textColor=colors.HexColor("#171717"),  
        alignment=TA_CENTER,  
        spaceAfter=20  
    )  
    flowables.append(Paragraph(title, title_style))  
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    flowables.append(Paragraph(f"Generated on: {date_str}", styles["NormalStyle"]))  
    flowables.append(Spacer(1, 20))  
      
    # Add logo if available  
    if os.path.exists("temp_logo.png"):  
        img = Image.open("temp_logo.png")  
        width, height = img.size  
        aspect_ratio = width / height  
        img_width = 2 * inch  
        img_height = img_width / aspect_ratio  
        rl_img = RLImage("temp_logo.png", width=img_width, height=img_height)  
        flowables.append(rl_img)  
        flowables.append(Spacer(1, 12))  
      
    # Add TIC plot  
    tic_img_bytes = tic_fig.to_image(format="png")  
    with open("tic_temp.png", "wb") as f:  
        f.write(tic_img_bytes)  
    rl_tic = RLImage("tic_temp.png", width=6*inch, height=3*inch)  
    flowables.append(Paragraph("Total Ion Chromatogram (TIC)", styles["HeaderStyle"]))  
    flowables.append(rl_tic)  
    flowables.append(Spacer(1, 12))  
      
    # Add overlaid EIC plots for each target mass  
    eic_img_bytes = eic_fig.to_image(format="png")  
    with open("eic_temp.png", "wb") as f:  
        f.write(eic_img_bytes)  
    rl_eic = RLImage("eic_temp.png", width=6*inch, height=3*inch)  
    masses_str = ", ".join(["{:.3f}".format(m) for m in target_masses])  
    flowables.append(Paragraph("Extracted Ion Chromatogram (EIC) for target masses: " + masses_str + " (±" + str(tolerance) + ")", styles["HeaderStyle"]))  
    flowables.append(rl_eic)  
    flowables.append(Spacer(1, 12))  
      
    # Add a table of mass spectra (first 10 rows for brevity)  
    flowables.append(Paragraph("Mass Spectra (sample)", styles["HeaderStyle"]))  
    sample_df = mass_df.head(10)  
    data = [sample_df.columns.to_list()] + sample_df.values.tolist()  
    table = Table(data)  
      
    # Fixed: Use individual color objects for each style element  
    tbl_style = TableStyle([  
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),  
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),  
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)  
    ])  
    table.setStyle(tbl_style)  
    flowables.append(table)  
      
    doc.build(flowables)  
    pdf_buffer.seek(0)  
    return pdf_buffer  
  
def get_download_link(pdf_buffer, base_filename):  
    b64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')  
    download_link = f'<a class="download-button" href="data:application/pdf;base64,{b64_pdf}" download="{base_filename}_report.pdf">Download PDF Report</a>'  
    return download_link  
  
# -----------------------------------------------  
# MS2 Spectral Matching Tab  
# -----------------------------------------------  
with tabs[1]:  
    st.header("MS2 Spectral Matching")  
    st.markdown("This tab demonstrates MS2 spectral matching (dummy implementation).")  
    query_input = st.text_input("Enter spectral intensities (comma-separated)", "100,200,150")  
    if query_input:  
        try:  
            query_intensities = [float(x.strip()) for x in query_input.split(",")]  
            # Dummy spectral matching: sort by sum of intensities (just for demonstration)  
            library_spectra = [  
                ('Spectrum_A', np.random.uniform(0.8, 1.0)),  
                ('Spectrum_B', np.random.uniform(0.5, 0.8)),  
                ('Spectrum_C', np.random.uniform(0.2, 0.5))  
            ]  
            results = sorted(library_spectra, key=lambda x: x[1], reverse=True)  
            st.markdown("### Matching Results")  
            if results:  
                results_df = pd.DataFrame(results, columns=["Spectrum Name", "Similarity Score"])  
                results_df["Similarity Score"] = results_df["Similarity Score"].apply(lambda x: round(x, 3))  
                st.dataframe(results_df)  
                  
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
  
# -----------------------------------------------  
# mzML Viewer Tab  
# -----------------------------------------------  
with tabs[0]:  
    st.header("mzML Viewer")  
    st.markdown("Upload an mzML file to view its chromatogram, extract ions based on target masses, and generate a PDF report.")  
    uploaded_file = st.file_uploader("Upload mzML File", type=["mzML"])  
      
    if uploaded_file is not None:  
        try:  
            # Save uploaded mzML file temporarily  
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
              
            # Input for target masses - MOVED ABOVE the EIC display  
            target_mass_input = st.text_input("Enter target mass values (comma-separated)", "400.0, 500.0")  
            tolerance = st.number_input("Mass tolerance (±)", min_value=0.01, max_value=10.0, value=0.5, step=0.1)  
              
            # Parse target masses  
            try:  
                target_masses = [float(mass.strip()) for mass in target_mass_input.split(",")]  
                  
                # Plot EIC for each target mass  
                eic_fig = go.Figure()  
                  
                # Color palette for multiple traces  
                colors = ["#2563EB", "#24EB84", "#B2EB24", "#EB3424", "#D324EB"]  
                  
                for i, target_mass in enumerate(target_masses):  
                    eic_times, eic_intensities = extract_eic(exp, target_mass, tolerance)  
                    color_idx = i % len(colors)  
                    eic_fig.add_trace(go.Scatter(  
                        x=eic_times,   
                        y=eic_intensities,   
                        mode='lines',   
                        name=f"m/z {target_mass:.3f}",  
                        line=dict(color=colors[color_idx])  
                    ))  
                  
                eic_fig.update_layout(  
                    title=f"Extracted Ion Chromatogram (EIC) for Target Masses (±{tolerance})",  
                    xaxis_title="Retention Time (s)",  
                    yaxis_title="Intensity",  
                    plot_bgcolor="#FFFFFF",  
                    paper_bgcolor="#FFFFFF"  
                )  
                  
                # Display EIC plot BELOW the mass selection inputs  
                st.plotly_chart(eic_fig)  
                  
                # Display mass spectra data  
                st.markdown("### Mass Spectra Data (Sample)")  
                st.dataframe(mass_df.head())  
                  
                # Generate PDF report  
                if st.button("Generate PDF Report"):  
                    try:  
                        pdf_buffer = create_pdf_report(tic_fig, eic_fig, mass_df, target_masses, tolerance, pdf_title_input)  
                        st.markdown(get_download_link(pdf_buffer, "mzml_analysis"), unsafe_allow_html=True)  
                        st.success("PDF report generated successfully!")  
                    except Exception as e:  
                        st.error(f"Error generating PDF report: {str(e)}")  
                          
            except ValueError as e:  
                st.error(f"Invalid mass input: {str(e)}")  
                  
        except Exception as e:  
            st.error(f"Error processing mzML file: {str(e)}")  
