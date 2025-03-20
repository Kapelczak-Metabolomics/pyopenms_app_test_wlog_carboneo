# Streamlit app that installs missing dependencies on the fly and loads an mzML file to view its chromatogram  
  
import sys  
import subprocess  
  
# Function to install a package if not present  
def install_if_missing(package):  
    try:  
        __import__(package)  
    except ImportError:  
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])  
  
# Install necessary packages  
install_if_missing("plotly")  
install_if_missing("pyopenms")  
install_if_missing("streamlit")  
  
# Now import the installed libraries  
import streamlit as st  
import plotly.graph_objects as go  
from pyopenms import MSExperiment, MzMLFile  
  
# Function to load an mzML file and extract chromatogram data  
def load_mzml_file(file_bytes):  
    # Create an MSExperiment instance  
    exp = MSExperiment()  
    # Use MzMLFile to load the file from a bytes object.  
    # Write the bytes to a temporary file since pyopenms requires a filename.  
    with open("temp.mzML", "wb") as f:  
        f.write(file_bytes)  
    mzml_file = MzMLFile()  
    mzml_file.load("temp.mzML", exp)  
    return exp  
  
# Function to extract chromatogram data from the experiment  
def extract_chromatogram(exp):  
    # Check if any chromatograms are present and then extract the first one.  
    chromatograms = exp.getChromatograms()  
    if len(chromatograms) == 0:  
        return None, None  
    chrom = chromatograms[0]  
    times = [p.getRT() for p in chrom.get_peaks()]  
    intensities = [p.getIntensity() for p in chrom.get_peaks()]  
    return times, intensities  
  
# Configure the Streamlit page  
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
      
    # Extract and validate chromatogram data  
    times, intensities = extract_chromatogram(experiment)  
      
    if times is None or intensities is None:  
        st.error("No chromatogram data found in this mzML file.")  
    else:  
        # Create interactive Plotly figure  
        fig = go.Figure()  
        fig.add_trace(go.Scatter(  
            x=times,  
            y=intensities,  
            mode="lines+markers",  
            line=dict(color="#2563EB"),  
            marker=dict(color="#D324EB")  
        ))  
        fig.update_layout(  
            title=dict(text="Chromatogram", x=0.5, xanchor="center", font=dict(size=20, color="#171717")),  
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
else:  
    st.info("Please upload an mzML file to begin.")  
