# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
import io  
import base64  
from datetime import datetime  
from pyopenms import MSExperiment, MzMLFile  
from reportlab.lib.pagesizes import letter  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle  
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors  
from reportlab.lib.units import inch  
  
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
        'Retention Time (s)': all_rts,  
        'Intensity': all_intensities  
    })  
      
    return df  
  
# Function to extract a specific mass peak  
def extract_mass_peak(df, target_mass, tolerance):  
    # Filter the DataFrame for the specified mass within the tolerance  
    filtered_df = df[(df['Mass (m/z)'] >= target_mass - tolerance) &   
                     (df['Mass (m/z)'] <= target_mass + tolerance)]  
      
    # Group by retention time and sum intensities  
    peak_data = filtered_df.groupby('Retention Time (s)')['Intensity'].sum().reset_index()  
      
    return peak_data  
  
# Function to create a downloadable PDF report  
def create_pdf_report(filename, tic_fig, eic_fig, target_mass, tolerance, mass_data):  
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
    elements.append(Paragraph(f"mzML Analysis Report: {filename}", title_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add date and time  
    date_style = ParagraphStyle(  
        'Date',  
        parent=styles['Normal'],  
        fontSize=10,  
        alignment=1,  
        spaceAfter=12  
    )  
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    elements.append(Paragraph(f"Generated on: {current_time}", date_style))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add TIC section  
    elements.append(Paragraph("Total Ion Chromatogram (TIC)", styles['Heading2']))  
    elements.append(Spacer(1, 0.1*inch))  
      
    # Save TIC figure to image and add to PDF  
    tic_img_bytes = io.BytesIO()  
    tic_fig.write_image(tic_img_bytes, format='png', width=600, height=400)  
    tic_img_bytes.seek(0)  
    elements.append(Image(tic_img_bytes, width=6*inch, height=4*inch))  
    elements.append(Spacer(1, 0.25*inch))  
      
    # Add EIC section if available  
    if eic_fig is not None:  
        elements.append(Paragraph(f"Extracted Ion Chromatogram (EIC) for m/z {target_mass} ± {tolerance}", styles['Heading2']))  
        elements.append(Spacer(1, 0.1*inch))  
          
        # Save EIC figure to image and add to PDF  
        eic_img_bytes = io.BytesIO()  
        eic_fig.write_image(eic_img_bytes, format='png', width=600, height=400)  
        eic_img_bytes.seek(0)  
        elements.append(Image(eic_img_bytes, width=6*inch, height=4*inch))  
        elements.append(Spacer(1, 0.25*inch))  
      
    # Add mass data table  
    elements.append(Paragraph("Top Mass Peaks", styles['Heading2']))  
    elements.append(Spacer(1, 0.1*inch))  
      
    # Prepare table data  
    table_data = [['Mass (m/z)', 'Retention Time (s)', 'Intensity']]  
    for _, row in mass_data.head(10).iterrows():  
        table_data.append([  
            f"{row['Mass (m/z)']:.4f}",  
            f"{row['Retention Time (s)']:.2f}",  
            f"{row['Intensity']:.0f}"  
        ])  
      
    # Create table  
    table = Table(table_data, colWidths=[2*inch, 2*inch, 2*inch])  
    table.setStyle(TableStyle([  
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),  
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),  
        ('GRID', (0, 0), (-1, -1), 1, colors.black)  
    ]))  
    elements.append(table)  
      
    # Build PDF  
    doc.build(elements)  
    buffer.seek(0)  
    return buffer  
  
# Function to create a download link  
def get_download_link(buffer, filename, text):  
    b64 = base64.b64encode(buffer.getvalue()).decode()  
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'  
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
        # Add a toggle for showing/hiding data points in TIC  
        show_points_tic = st.checkbox("Show individual data points in TIC", value=True)  
          
        # Create interactive Plotly figure for TIC  
        fig_tic = go.Figure()  
          
        # Determine the mode based on the toggle  
        mode_tic = "lines+markers" if show_points_tic else "lines"  
          
        fig_tic.add_trace(go.Scatter(  
            x=times,  
            y=intensities,  
            mode=mode_tic,  
            line=dict(color="#2563EB"),  
            marker=dict(color="#D324EB", size=6)  
        ))  
          
        fig_tic.update_layout(  
            title=dict(text="Total Ion Chromatogram (TIC)", x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
            xaxis_title="Retention Time (s)",  
            yaxis_title="Intensity",  
            xaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False, ticks="outside", linecolor="#171717"),  
            plot_bgcolor="#FFFFFF",  
            paper_bgcolor="#FFFFFF",  
            font=dict(family="Inter", size=14, color="#171717"),  
            margin=dict(l=60, r=40, t=60, b=60)  
        )  
          
        st.plotly_chart(fig_tic, use_container_width=True)  
          
        # Extract mass spectra data  
        with st.spinner("Extracting mass spectra data..."):  
            mass_data = extract_mass_spectra(experiment)  
          
        if not mass_data.empty:  
            # Display a table of masses  
            st.subheader("Mass Peaks")  
              
            # Group by mass and sum intensities  
            grouped_masses = mass_data.groupby('Mass (m/z)')['Intensity'].sum().reset_index()  
            grouped_masses = grouped_masses.sort_values('Intensity', ascending=False)  
              
            # Get retention time for each mass (using the max intensity instance)  
            mass_rt_map = {}  
            for mass in grouped_masses['Mass (m/z)'].unique():  
                mass_subset = mass_data[mass_data['Mass (m/z)'] == mass]  
                max_intensity_idx = mass_subset['Intensity'].idxmax()  
                mass_rt_map[mass] = mass_data.loc[max_intensity_idx, 'Retention Time (s)']  
              
            grouped_masses['Retention Time (s)'] = grouped_masses['Mass (m/z)'].map(mass_rt_map)  
              
            # Limit to top 100 masses if there are too many  
            if len(grouped_masses) > 100:  
                display_masses = grouped_masses.head(100)  
                st.info(f"Showing top 100 masses by intensity out of {len(grouped_masses)} total masses.")  
            else:  
                display_masses = grouped_masses  
              
            st.dataframe(display_masses)  
              
            # Add section for extracting a specific mass peak  
            st.subheader("Extract Mass Peak")  
              
            col1, col2, col3 = st.columns([2, 1, 1])  
              
            with col1:  
                # Input for target mass  
                min_mass = float(mass_data['Mass (m/z)'].min())  
                max_mass = float(mass_data['Mass (m/z)'].max())  
                target_mass = st.number_input(  
                    "Enter mass (m/z):",  
                    min_value=min_mass,  
                    max_value=max_mass,  
                    value=(min_mass + max_mass) / 2,  
                    step=0.1,  
                    format="%.4f"  
                )  
              
            with col2:  
                # Input for mass tolerance  
                tolerance = st.number_input(  
                    "Tolerance (±):",  
                    min_value=0.0001,  
                    max_value=1.0,  
                    value=0.1,  
                    step=0.01,  
                    format="%.4f"  
                )  
              
            with col3:  
                # Button to extract the peak  
                extract_button = st.button("Extract Peak")  
              
            # Variable to store the extracted peak figure  
            fig_peak = None  
              
            if extract_button:  
                # Extract the peak data  
                peak_data = extract_mass_peak(mass_data, target_mass, tolerance)  
                  
                if not peak_data.empty:  
                    # Add a toggle for showing/hiding data points in EIC  
                    show_points_eic = st.checkbox("Show individual data points in EIC", value=True)  
                      
                    # Determine the mode based on the toggle  
                    mode_eic = "lines+markers" if show_points_eic else "lines"  
                      
                    # Create a figure for the extracted peak  
                    fig_peak = go.Figure()  
                    fig_peak.add_trace(go.Scatter(  
                        x=peak_data['Retention Time (s)'],  
                        y=peak_data['Intensity'],  
                        mode=mode_eic,  
                        line=dict(color="#24EB84"),  
                        marker=dict(color="#B2EB24", size=6)  
                    ))  
                      
                    fig_peak.update_layout(  
                        title=dict(  
                            text=f"Extracted Ion Chromatogram (EIC) for m/z {target_mass:.4f} ± {tolerance:.4f}",  
                            x=0.5,  
                            xanchor="center",  
                            font=dict(size=20, color="#171717")  
                        ),  
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
                      
                    # Add option to generate PDF report  
                    st.subheader("Generate Report")  
                      
                    if st.button("Generate PDF Report"):  
                        with st.spinner("Generating PDF report..."):  
                            # Create PDF report  
                            pdf_buffer = create_pdf_report(  
                                uploaded_file.name,  
                                fig_tic,  
                                fig_peak,  
                                target_mass,  
                                tolerance,  
                                display_masses  
                            )  
                              
                            # Create download link  
                            report_filename = f"mzml_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"  
                            download_link = get_download_link(pdf_buffer, report_filename, "Download PDF Report")  
                              
                            # Display download link  
                            st.markdown(download_link, unsafe_allow_html=True)  
                            st.success("PDF report generated successfully!")  
                else:  
                    st.warning(f"No data found for mass {target_mass:.4f} ± {tolerance:.4f}")  
        else:  
            st.error("No mass spectra data found in this mzML file.")  
else:  
    st.info("Please upload an mzML file to begin.")  
