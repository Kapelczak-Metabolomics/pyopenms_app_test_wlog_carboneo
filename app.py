# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
  
# Check if reportlab is installed, if not, inform the user  
try:  
    from reportlab.lib.pagesizes import letter  
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle  
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
    from reportlab.lib import colors  
    from reportlab.lib.units import inch  
    reportlab_available = True  
except ImportError:  
    reportlab_available = False  
    st.warning("ReportLab is not installed. PDF report generation will be disabled. Please add 'reportlab' to your requirements.txt file.")  
  
# Function to load an mzML file and extract chromatogram data  
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
  
# Function to extract chromatogram data from the experiment  
def extract_chromatogram(exp):  
    chromatograms = exp.getChromatograms()  
    if len(chromatograms) == 0:  
        return None, None  
    chrom = chromatograms[0]  
    peaks = chrom.get_peaks()  
    # If the returned peaks are a tuple (common when using NumPy arrays),  
    # assume peaks[0] is the time values and peaks[1] is the intensity values.  
    if isinstance(peaks, tuple):  
        times, intensities = peaks  
    else:  
        # Otherwise, assume a list where each element has methods getRT() and getIntensity()  
        times = [p.getRT() for p in peaks]  
        intensities = [p.getIntensity() for p in peaks]  
    return times, intensities  
  
# Function to extract mass spectra data  
def extract_mass_spectra(exp):  
    # Get all spectra from the experiment  
    spectra = exp.getSpectra()  
      
    # Initialize lists to store data  
    all_masses = []  
    all_intensities = []  
    all_rts = []  
      
    # Extract data from each spectrum  
    for spectrum in spectra:  
        rt = spectrum.getRT()  # Retention time  
        mz_array, intensity_array = spectrum.get_peaks()  
          
        # Add data to lists  
        for i in range(len(mz_array)):  
            all_masses.append(mz_array[i])  
            all_intensities.append(intensity_array[i])  
            all_rts.append(rt)  
      
    # Create a DataFrame  
    df = pd.DataFrame({  
        'Mass (m/z)': all_masses,  
        'Intensity': all_intensities,  
        'Retention Time (s)': all_rts  
    })  
      
    return df  
  
# Function to extract a specific mass peak  
def extract_mass_peak(df, target_mass, tolerance):  
    # Filter the DataFrame for the target mass within the tolerance  
    filtered_df = df[(df['Mass (m/z)'] >= target_mass - tolerance) &   
                     (df['Mass (m/z)'] <= target_mass + tolerance)]  
      
    if filtered_df.empty:  
        return None  
      
    # Group by retention time and sum intensities  
    peak_data = filtered_df.groupby('Retention Time (s)')['Intensity'].sum().reset_index()  
      
    return peak_data  
  
# Function to create a PDF report  
def create_pdf_report(filename, tic_times, tic_intensities, eic_data=None, target_mass=None, tolerance=None, mass_data=None):  
    if not reportlab_available:  
        return None  
          
    buffer = io.BytesIO()  
    doc = SimpleDocTemplate(buffer, pagesize=letter)  
    styles = getSampleStyleSheet()  
    elements = []  
      
    # Add title  
    title_style = ParagraphStyle(  
        'Title',  
        parent=styles['Heading1'],  
        fontSize=16,  
        alignment=1,  
        spaceAfter=12  
    )  
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    elements.append(Paragraph(f"mzML Analysis Report: {filename}", title_style))  
    elements.append(Paragraph(f"Generated: {timestamp}", styles['Normal']))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Save TIC plot to a temporary file  
    tic_fig = go.Figure()  
    tic_fig.add_trace(go.Scatter(  
        x=tic_times,  
        y=tic_intensities,  
        mode="lines",  
        line=dict(color="#2563EB")  
    ))  
    tic_fig.update_layout(  
        title="Total Ion Chromatogram",  
        xaxis_title="Retention Time (s)",  
        yaxis_title="Intensity",  
        plot_bgcolor="#FFFFFF"  
    )  
    tic_img_bytes = tic_fig.to_image(format="png", width=600, height=400)  
      
    # Add TIC plot to the report  
    elements.append(Paragraph("Total Ion Chromatogram", styles['Heading2']))  
    elements.append(Spacer(1, 0.1*inch))  
    img = Image(io.BytesIO(tic_img_bytes), width=6*inch, height=4*inch)  
    elements.append(img)  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add EIC plot if available  
    if eic_data is not None and not eic_data.empty:  
        elements.append(Paragraph(f"Extracted Ion Chromatogram for m/z {target_mass:.4f} ± {tolerance:.4f}", styles['Heading2']))  
        elements.append(Spacer(1, 0.1*inch))  
          
        eic_fig = go.Figure()  
        eic_fig.add_trace(go.Scatter(  
            x=eic_data['Retention Time (s)'],  
            y=eic_data['Intensity'],  
            mode="lines",  
            line=dict(color="#24EB84")  
        ))  
        eic_fig.update_layout(  
            xaxis_title="Retention Time (s)",  
            yaxis_title="Intensity",  
            plot_bgcolor="#FFFFFF"  
        )  
        eic_img_bytes = eic_fig.to_image(format="png", width=600, height=400)  
          
        img = Image(io.BytesIO(eic_img_bytes), width=6*inch, height=4*inch)  
        elements.append(img)  
        elements.append(Spacer(1, 0.25*inch))  
      
    # Add mass data table if available  
    if mass_data is not None and not mass_data.empty:  
        elements.append(Paragraph("Top Mass Peaks by Intensity", styles['Heading2']))  
        elements.append(Spacer(1, 0.1*inch))  
          
        # Get top 10 masses by intensity  
        top_masses = mass_data.sort_values('Intensity', ascending=False).head(10)  
          
        # Create table data  
        table_data = [['Mass (m/z)', 'Retention Time (s)', 'Intensity']]  
        for _, row in top_masses.iterrows():  
            table_data.append([  
                f"{row['Mass (m/z)']:.4f}",  
                f"{row['Retention Time (s)']:.2f}",  
                f"{row['Intensity']:.0f}"  
            ])  
          
        # Create table  
        table = Table(table_data, colWidths=[2*inch, 2*inch, 2*inch])  
        table.setStyle(TableStyle([  
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),  
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),  
            ('GRID', (0, 0), (-1, -1), 1, colors.black)  
        ]))  
          
        elements.append(table)  
      
    # Build the PDF  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
# Function to create a download link for the PDF  
def get_download_link(buffer, filename):  
    b64 = base64.b64encode(buffer.getvalue()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF Report</a>'  
    return href  
  
# Setup Streamlit app page  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram.")  
  
# File uploader widget  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Extract and display the total ion chromatogram  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        st.header("Total Ion Chromatogram")  
          
        # Add a toggle for showing/hiding data points  
        show_points = st.checkbox("Show individual data points on TIC", value=True)  
          
        # Create interactive Plotly figure for chromatogram  
        fig = go.Figure()  
          
        # Determine the mode based on the toggle  
        mode = "lines+markers" if show_points else "lines"  
          
        fig.add_trace(go.Scatter(  
            x=times,  
            y=intensities,  
            mode=mode,  
            line=dict(color="#2563EB"),  
            marker=dict(color="#D324EB", size=6)  
        ))  
          
        fig.update_layout(  
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
          
        st.plotly_chart(fig, use_container_width=True)  
          
        # Extract and display mass spectra data  
        with st.spinner("Extracting mass spectra data..."):  
            mass_data = extract_mass_spectra(experiment)  
          
        if not mass_data.empty:  
            st.header("Mass Spectra Data")  
              
            # Display a table of unique masses  
            unique_masses = mass_data.sort_values('Intensity', ascending=False).drop_duplicates(subset=['Mass (m/z)'])  
            if len(unique_masses) > 100:  
                st.info(f"Found {len(unique_masses)} unique masses. Showing top 100 by intensity.")  
                unique_masses = unique_masses.head(100)  
              
            st.dataframe(unique_masses)  
              
            # Add mass extraction section  
            st.header("Extract Specific Mass")  
              
            col1, col2, col3 = st.columns([2, 1, 1])  
              
            with col1:  
                min_mass = mass_data['Mass (m/z)'].min()  
                max_mass = mass_data['Mass (m/z)'].max()  
                target_mass = st.number_input(  
                    "Enter mass (m/z) to extract:",  
                    min_value=float(min_mass),  
                    max_value=float(max_mass),  
                    value=float((min_mass + max_mass) / 2),  
                    step=0.1,  
                    format="%.4f"  
                )  
              
            with col2:  
                tolerance = st.number_input(  
                    "Mass tolerance (±):",  
                    min_value=0.0001,  
                    max_value=1.0,  
                    value=0.1,  
                    step=0.01,  
                    format="%.4f"  
                )  
              
            with col3:  
                extract_button = st.button("Extract Peak")  
              
            if extract_button:  
                with st.spinner(f"Extracting peak for mass {target_mass:.4f} ± {tolerance:.4f}..."):  
                    peak_data = extract_mass_peak(mass_data, target_mass, tolerance)  
                  
                if peak_data is not None and not peak_data.empty:  
                    st.subheader(f"Extracted Ion Chromatogram for m/z {target_mass:.4f} ± {tolerance:.4f}")  
                      
                    # Add a toggle for showing/hiding data points on EIC  
                    show_points_eic = st.checkbox("Show individual data points on EIC", value=True)  
                      
                    # Create figure for the extracted peak  
                    fig_peak = go.Figure()  
                      
                    # Determine the mode based on the toggle  
                    mode_eic = "lines+markers" if show_points_eic else "lines"  
                      
                    fig_peak.add_trace(go.Scatter(  
                        x=peak_data['Retention Time (s)'],  
                        y=peak_data['Intensity'],  
                        mode=mode_eic,  
                        line=dict(color="#24EB84"),  
                        marker=dict(color="#B2EB24", size=6)  
                    ))  
                      
                    fig_peak.update_layout(  
                        xaxis_title="Retention Time (s)",  
                        yaxis_title="Intensity",  
                        xaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
                        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
                        plot_bgcolor="#FFFFFF",  
                        paper_bgcolor="#FFFFFF",  
                        font=dict(family="Inter", size=14, color="#171717"),  
                        margin=dict(l=60, r=40, t=60, b=60)  
                    )  
                      
                    st.plotly_chart(fig_peak, use_container_width=True)  
                      
                    # PDF Report Generation Section  
                    if reportlab_available:  
                        st.header("Generate Report")  
                          
                        if st.button("Generate PDF Report"):  
                            with st.spinner("Generating PDF report..."):  
                                pdf_buffer = create_pdf_report(  
                                    uploaded_file.name,  
                                    times,  
                                    intensities,  
                                    peak_data,  
                                    target_mass,  
                                    tolerance,  
                                    mass_data  
                                )  
                                  
                                if pdf_buffer:  
                                    # Create a timestamp for the filename  
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  
                                    filename = f"mzml_report_{timestamp}.pdf"  
                                      
                                    # Create download link  
                                    download_link = get_download_link(pdf_buffer, filename)  
                                      
                                    # Display download link  
                                    st.markdown(download_link, unsafe_allow_html=True)  
                                    st.success("PDF report generated successfully!")  
                else:  
                    st.warning(f"No data found for mass {target_mass:.4f} ± {tolerance:.4f}")  
        else:  
            st.error("No mass spectra data found in this mzML file.")  
else:  
    st.info("Please upload an mzML file to begin.")  
