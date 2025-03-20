# Import necessary libraries  
import streamlit as st  
import plotly.graph_objects as go  
import numpy as np  
import pandas as pd  
from pyopenms import MSExperiment, MzMLFile  
  
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
def extract_mass_peak(df, target_mass, tolerance=0.1):  
    # Filter data for the specified mass within tolerance  
    filtered_df = df[(df['Mass (m/z)'] >= target_mass - tolerance) &   
                     (df['Mass (m/z)'] <= target_mass + tolerance)]  
      
    if filtered_df.empty:  
        return None  
      
    # Group by retention time and sum intensities  
    peak_data = filtered_df.groupby('Retention Time (s)')['Intensity'].sum().reset_index()  
      
    return peak_data  
  
# Setup Streamlit app page  
st.set_page_config(page_title="mzML Chromatogram Viewer", layout="wide")  
st.title("mzML Chromatogram Viewer")  
st.markdown("Upload an mzML file to view its corresponding chromatogram and mass spectra.")  
  
# File uploader widget  
uploaded_file = st.file_uploader("Choose an mzML file", type=["mzML"])  
  
if uploaded_file is not None:  
    file_bytes = uploaded_file.read()  
    with st.spinner("Loading mzML file..."):  
        experiment = load_mzml_file(file_bytes)  
    st.success("File loaded successfully!")  
      
    # Extract and display the chromatogram  
    times, intensities = extract_chromatogram(experiment)  
    if times is None or intensities is None:  
        st.warning("No chromatogram data found in this mzML file. Proceeding with mass spectra analysis.")  
    else:  
        # Add a toggle for showing/hiding data points  
        show_points = st.checkbox("Show individual data points", value=True)  
          
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
      
    # Extract mass spectra data  
    with st.spinner("Extracting mass spectra data..."):  
        mass_data = extract_mass_spectra(experiment)  
      
    if not mass_data.empty:  
        st.subheader("Mass Spectra Data")  
          
        # Create a summary of unique masses  
        unique_masses = mass_data['Mass (m/z)'].unique()  
          
        # If there are too many unique masses, sample them  
        if len(unique_masses) > 100:  
            # Sort by intensity and take top masses  
            top_masses = mass_data.groupby('Mass (m/z)')['Intensity'].max().sort_values(ascending=False).head(100).index.tolist()  
            mass_summary = mass_data[mass_data['Mass (m/z)'].isin(top_masses)]  
        else:  
            mass_summary = mass_data  
          
        # Group by mass and get max intensity and corresponding RT  
        mass_summary = mass_summary.sort_values('Intensity', ascending=False).drop_duplicates('Mass (m/z)')  
        mass_summary = mass_summary.sort_values('Mass (m/z)')  
          
        # Display the table  
        st.dataframe(mass_summary[['Mass (m/z)', 'Retention Time (s)', 'Intensity']].reset_index(drop=True))  
          
        # Add option to extract a specific mass peak  
        st.subheader("Extract Specific Mass Peak")  
          
        col1, col2 = st.columns([3, 1])  
        with col1:  
            target_mass = st.number_input("Enter mass (m/z) to extract:",   
                                         min_value=float(mass_data['Mass (m/z)'].min()),   
                                         max_value=float(mass_data['Mass (m/z)'].max()),  
                                         value=float(mass_data['Mass (m/z)'].iloc[0]))  
          
        with col2:  
            mass_tolerance = st.number_input("Mass tolerance (±):",   
                                            min_value=0.001,   
                                            max_value=1.0,   
                                            value=0.1)  
          
        if st.button("Extract Peak"):  
            peak_data = extract_mass_peak(mass_data, target_mass, mass_tolerance)  
              
            if peak_data is None or peak_data.empty:  
                st.error(f"No data found for mass {target_mass} ± {mass_tolerance}")  
            else:  
                st.success(f"Peak extracted for mass {target_mass} ± {mass_tolerance}")  
                  
                # Create a plot for the extracted peak  
                fig_peak = go.Figure()  
                fig_peak.add_trace(go.Scatter(  
                    x=peak_data['Retention Time (s)'],  
                    y=peak_data['Intensity'],  
                    mode="lines+markers",  
                    line=dict(color="#24EB84"),  
                    marker=dict(color="#B2EB24", size=6)  
                ))  
                  
                fig_peak.update_layout(  
                    title=dict(text=f"Extracted Ion Chromatogram (m/z {target_mass} ± {mass_tolerance})",   
                              x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
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
    else:  
        st.error("No mass spectra data found in this mzML file.")  
else:  
    st.info("Please upload an mzML file to begin.")  
