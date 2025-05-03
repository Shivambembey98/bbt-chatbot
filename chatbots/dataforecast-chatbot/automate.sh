#!/bin/bash

# Update system
sudo apt update
sudo apt upgrade -y

# Install dependencies
sudo apt install git python3 python3-pip python3-venv -y

# Clone repository
git clone https://github.com/AkshitVerma021/Dynamic-Forecasting-Vizualizer.git
cd Dynamic-Forecasting-Vizualizer

# Create virtual environment
python3 -m venv myenv
source myenv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Run Streamlit app
streamlit run main.py --server.address 0.0.0.0
