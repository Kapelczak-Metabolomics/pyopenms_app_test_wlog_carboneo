import streamlit as st
import pyopenms
import numpy as np
import matplotlib.pyplot as plt

st.title('MS1 Chromatogram Visualization')

# File upload
uploaded_file = st.file_uploader("Choose a mzML file", type=['mzML'])

if uploaded_file is not None:
    # Save the uploaded file temporarily
    with open("temp.mzML", "wb") as f:
        f.write(uploaded_file.getvalue())
    
    # Read the mzML file
    exp = pyopenms.MSExperiment()
    pyopenms.MzMLFile().load("temp.mzML", exp)
    
    # Extract TIC (Total Ion Chromatogram)
    times = []
    intensities = []
    
    for spectrum in exp:
        if spectrum.getMSLevel() == 1:  # MS1 level
            times.append(spectrum.getRT())
            intensities.append(sum(spectrum.get_peaks()[1]))
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(times, intensities)
    ax.set_xlabel('Retention Time (seconds)')
    ax.set_ylabel('Total Ion Current')
    ax.set_title('MS1 Total Ion Chromatogram')
    
    # Display the plot in Streamlit
    st.pyplot(fig)
    
    # Add some statistics
    st.write("File Statistics:")
    st.write(f"Number of spectra: {exp.size()}")
    st.write(f"RT range: {exp.getMinRT():.2f} to {exp.getMaxRT():.2f} seconds")
    
    # Cleanup
    import os
    if os.path.exists("temp.mzML"):
        os.remove("temp.mzML")
