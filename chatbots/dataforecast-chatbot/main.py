import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import chardet
import hashlib
import pdfplumber
import time
import logging
from dotenv import load_dotenv
from statsmodels.tsa.arima.model import ARIMA
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from auth import init_session_state, check_auth, sign_out, increment_usage, check_usage_limit, DATA_DIR, update_user_in_db
from chatbot import chatbot_section  
from prophet import Prophet
from plotly import graph_objs as go
from db_storage import save_forecast, load_forecast, save_chat_history, load_chat_history
from razorpay_payment import RazorpayPayment, display_payment_interface
from streamlit_javascript import st_javascript
query_params = st.query_params
page = query_params.get("token", [])# default to '1'
 
 

if page:
    st.set_page_config(page_title="Second Page")
    st.title("Redirecting to main page...")
    st_javascript(f"""localStorage.setItem("user_token", "{page}");""")
    # JavaScript redirect using meta refresh
    st.markdown("""
        <meta http-equiv="refresh" content="1; url=/dataforecast-chatbot/" />
    """, unsafe_allow_html=True)
    print("get token",page)
    st.session_state.page = page
    print("page",st.session_state.page)
    st.stop()  # Prevent rest of the script from running
else:
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Load environment variables from .env file
    load_dotenv()

    # Razorpay Configuration from environment variables
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    RAZORPAY_AMOUNT = int(os.getenv("RAZORPAY_AMOUNT", "100"))  # Default to 100 paise if not specified
    RAZORPAY_CURRENCY = os.getenv("RAZORPAY_CURRENCY", "INR")
    RAZORPAY_COMPANY_NAME = os.getenv("RAZORPAY_COMPANY_NAME", "Bell Blaze Technologies Pvt Ltd")
    RAZORPAY_DESCRIPTION = os.getenv("RAZORPAY_DESCRIPTION", "Premium Membership")

    # Initialize Razorpay payment handler
    razorpay_payment = RazorpayPayment(
        key_id=RAZORPAY_KEY_ID,
        key_secret=RAZORPAY_KEY_SECRET,
        amount=RAZORPAY_AMOUNT,
        currency=RAZORPAY_CURRENCY,
        company_name=RAZORPAY_COMPANY_NAME,
        description=RAZORPAY_DESCRIPTION
    )

    # 📌 Set Streamlit Page Config (MUST BE FIRST!)
    st.set_page_config(page_title="AI-Powered Data Analysis and Forecasting", layout="centered")

    # 📸 Add Company Logo at the Top
    st.markdown(
        """
        <style>
        .center-logo {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # 📸 Add Logo as Image (Centered Properly)
    col1, col2, col3 = st.columns([1, 1, 1])  # Use 1:2:1 ratio for perfect centering
    with col2:
        st.image("logo.png", width=275)

    # 📚 Load CSS for Custom Styling
    def load_css(styles):
        with open(styles, "r") as f:
            css_styles = f.read()
            st.markdown(f"<style>{css_styles}</style>", unsafe_allow_html=True)

    # Add custom CSS for centered title
    st.markdown(
        """
        <style>
        .title-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 1rem;
        }
        .title-text {
            text-align: center;
            font-size: 2.5rem;
            font-weight: bold;
            color: #17a7e0;
        }
        /* Hide the default file size limit text - multiple selectors for different elements */
        .uploadedFile:first-child ~ small,
        .stFileUploader > section > div > small,
        .stFileUploader [data-testid="stFileUploadDropzone"] > div + div,
        div[data-testid="stFileUploadDropzone"] > div:nth-child(2),
        .stFileUploader p:nth-child(2),
        .stFileUploader small, 
        [data-testid="stFileUploadDropzone"] p + p,
        [data-testid="stFileUploadDropzone"] > div > p:not(:first-child),
        [data-testid="stFileUploadDropzone"] small,
        .stFileUploader .css-ysnqb2,
        .stFileUploader div + p {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            opacity: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    load_css("styles.css")

    # 🔥 App Title with centered styling
    st.markdown(
        """
        <div class="title-container">
            <div class="title-text">📊 AI-Powered Data Analysis and Forecasting</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Log storage information
    logger.info("Using PostgreSQL database for storage")

    # 🗄 Define Storage Directories - keep this as a placeholder but don't use for storage
    # STORAGE_DIR = os.path.join(DATA_DIR, "saved_forecasts")
    # MODEL_DIR = os.path.join(DATA_DIR, "saved_models")
    # CHAT_HISTORY_DIR = os.path.join(DATA_DIR, "chat_history")

    # 🔑 Initialize Session State
    init_session_state()


    # 🔐 Check Authentication (now just passes through)
    check_auth()

    # 📍 AWS Bedrock Client Initialization
    def get_bedrock_client():
        try:
            import boto3
            return boto3.client(service_name="bedrock-runtime", region_name="ap-south-1")
        except ImportError:
            logger.warning("boto3 not installed, Bedrock functionality will not work")
            return None
        except Exception as e:
            logger.error(f"Error initializing Bedrock client: {e}")
            return None

    try:
        bedrock_client = get_bedrock_client()
    except Exception as e:
        logger.error(f"Could not initialize Bedrock client: {e}")
        bedrock_client = None

    # Keep track of uploaded files to detect new uploads
    if "tracked_files" not in st.session_state:
        st.session_state.tracked_files = set()

    # 📥 Sidebar for Multiple File Uploads with Progress Bar
    st.sidebar.header("📂 Upload Your Datasets")

    # Add custom text to show 5MB limit
    st.sidebar.markdown(
        """
        <div style="color: #888888; font-size: 14px; margin-bottom: 10px;">
        </div>
        """,
        unsafe_allow_html=True
    )

    # Create a session state for controlling payment page display
    if "show_payment_page" not in st.session_state:
        st.session_state.show_payment_page = False

    # Display usage information
    FREE_USAGE_LIMIT = 6
    remaining_uses = max(0, FREE_USAGE_LIMIT - st.session_state.usage_count)

    # Show premium badge or remaining usage
    if st.session_state.paid_user:
        st.sidebar.success("💎 Premium User - Unlimited Access")
    else:
        if remaining_uses > 0:
            st.sidebar.info(f"🔄 {remaining_uses} free uses remaining")
        else:
            st.sidebar.warning("⚠️ Free usage limit reached")

    # Add Sign-Out Button in the sidebar (moved before Premium button)
    st.sidebar.markdown(
        """
        <a href="https://www.bellblazetech.com/our-solutions" target="_blank">
            <button style="
                background-color: #17a7e0;
                color: white;
                border: none;
                width: 100%;
                padding: 8px 15px;
                margin-top: 10px;
                margin-bottom: 10px;
                border-radius: 5px;
                font-weight: bold;
                cursor: pointer;
            ">
                Sign Out
            </button>
        </a>
        """,
        unsafe_allow_html=True
    )

    # Function to toggle payment page
    def toggle_payment_page():
        st.session_state.show_payment_page = not st.session_state.show_payment_page
        
        # If opening payment page, set a flag to track where the user came from
        if st.session_state.show_payment_page:
            # Store current app state to restore after payment
            if 'return_from_payment' not in st.session_state:
                st.session_state.return_from_payment = False

    # Add subscription button after Sign Out
    st.sidebar.button("💎 Upgrade to Premium", on_click=toggle_payment_page, use_container_width=True)

    # Display payment page if toggled
    if st.session_state.show_payment_page:
        # Create a sidebar container for the payment interface
        with st.sidebar:
            st.markdown("## 💳 Upgrade to Premium")
            st.markdown("""
            ### Benefits of Premium:
            - ✅ Unlimited data analysis
            - ✅ Priority support
            - ✅ Advanced forecasting models
            """)
            
            # Display Razorpay payment interface
            payment_verified = display_payment_interface(razorpay_payment)
            
            # If payment is verified, set user as premium and close payment page
            if payment_verified:
                st.session_state.paid_user = True
                # Save premium status to database
                update_user_in_db()
                st.session_state.show_payment_page = False
                st.session_state.return_from_payment = True
                st.success("🎉 Payment completed successfully! You now have premium access.")
                st.balloons()
                time.sleep(1)
                st.rerun()
        
        # Don't stop execution when payment page is in sidebar
        # This allows the main content to still be visible

    # 📚 Load Uploaded Files
    dataframes = []
    file_names = []

    # Check if user has reached their usage limit before showing the uploader
    has_reached_limit = not check_usage_limit() and not st.session_state.paid_user

    # Only show file uploader if user has not reached their limit or is a premium user
    if not has_reached_limit:
        uploaded_files = st.sidebar.file_uploader(
            "Upload Files (CSV, Excel, JSON, Parquet, PDF)",
            type=["csv", "xls", "xlsx", "json", "parquet", "pdf"],  
            accept_multiple_files=True
        )

        # Progress Bar for File Upload
        progress_bar = st.sidebar.progress(0)

        if uploaded_files:
            total_files = len(uploaded_files)
            for i, uploaded_file in enumerate(uploaded_files):
                file_name = uploaded_file.name
                file_size = len(uploaded_file.getvalue())  # Get file size in bytes
                
                # Check if this is a new file we haven't tracked yet
                file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
                file_identifier = f"{file_name}_{file_hash}"
                
                # If this is a new file, count it as usage
                if file_identifier not in st.session_state.tracked_files:
                    st.session_state.tracked_files.add(file_identifier)
                    increment_usage()
                    
                    # Check if user just hit their limit with this new upload
                    if not check_usage_limit() and not st.session_state.paid_user:
                        st.warning("⚠️ You've reached your free usage limit (6 uses). Please upgrade to continue using the application.")
                        st.session_state.show_payment_page = True
                        st.rerun()
                
                # 📏 Check File Size (Limit: 5MB)
                if file_size > 5 * 1024 * 1024:  # 5MB limit
                    st.sidebar.error(f"❌ {file_name} exceeds 5MB size limit. Skipping file.")
                    continue
                st.sidebar.write(f"✅ {file_name} uploaded successfully.")
                progress_bar.progress((i + 1) / total_files)

                # Load CSV/Excel/JSON/Parquet/PDF
                # Reset file pointer after calculating hash
                uploaded_file.seek(0)
                raw_data = uploaded_file.read()
                encoding_type = chardet.detect(raw_data)["encoding"]
                uploaded_file.seek(0)

                try:
                    if file_name.endswith(".csv"):
                        df = pd.read_csv(uploaded_file, encoding=encoding_type, encoding_errors="replace")
                    elif file_name.endswith((".xls", ".xlsx")):
                        df = pd.read_excel(uploaded_file)
                    elif file_name.endswith(".json"):
                        df = pd.read_json(uploaded_file)
                    elif file_name.endswith(".parquet"):
                        df = pd.read_parquet(uploaded_file)
                    elif file_name.endswith(".pdf"):
                        # 📄 Extract Text from PDF Using pdfplumber
                        with pdfplumber.open(uploaded_file) as pdf:
                            text = ""
                            for page in pdf.pages:
                                text += page.extract_text()

                        # 📄 Convert PDF Text to DataFrame (Line by Line)
                        lines = text.split("\n")
                        df = pd.DataFrame({"Text": lines})
                    else:
                        st.sidebar.error(f"❌ Unsupported file format: {file_name}")
                        continue

                    dataframes.append(df)
                    file_names.append(file_name)
                except Exception as e:
                    st.sidebar.error(f"❌ Error loading {file_name}: {str(e)}")
                    continue

            # Reset Progress Bar
            progress_bar.progress(0)

    else:
        # If user has reached the limit, show upgrade message
        st.warning("⚠️ You've reached your free usage limit (6 uses). Please upgrade to continue using the application.")
        
        # Force show the payment page
        if not st.session_state.show_payment_page:
            st.session_state.show_payment_page = True
            st.rerun()

    # Only process files and show visualizations if user has not reached their limit
    if not has_reached_limit:
        # ✅ Dropdown to Select File and View Option
        if dataframes:
            selected_file = st.selectbox(
                "📂 Select a file to view",
                file_names,
                index=0
            )

            # Get the corresponding dataframe
            selected_df = dataframes[file_names.index(selected_file)]

            # Track if chart view has been counted for usage in this session
            if "chart_view_counted" not in st.session_state:
                st.session_state.chart_view_counted = False

            # 📊 Choose Between Preview and Chart
            option = st.selectbox(
                f"📊 Select View for `{selected_file}`",
                ["📋 Preview", "📈 Chart"]
            )

            if option == "📋 Preview":
                st.write(f"### 📋 Preview of `{selected_file}`")
                if selected_file.endswith(".pdf"):
                    st.text_area("📄 PDF Content", "\n".join(selected_df["Text"].tolist()), height=400)
                else:
                    st.dataframe(selected_df.head(50))

            elif option == "📈 Chart":
                # Count chart view for usage if not already counted in this session
                if not st.session_state.chart_view_counted:
                    increment_usage()
                    st.session_state.chart_view_counted = True
                    
                    # Check if user just hit their limit with this chart view
                    if not check_usage_limit() and not st.session_state.paid_user:
                        st.warning("⚠️ You've reached your free usage limit (6 uses). Please upgrade to continue using the application.")
                        st.session_state.show_payment_page = True
                        st.rerun()
                
                # Replace the existing date column detection code with this enhanced version
                date_column_keywords = ["year", "date", "age", "month", "time", "period", "quarter", "yr", "day"]
                numeric_time_indicators = ["year", "age", "period", "Year", "Age", "yr"]
                
                # Initialize date_col as None
                date_col = None
                
                # First try to find datetime columns
                for col in selected_df.columns:
                    try:
                        col_lower = col.lower()
                        
                        # Check if column name contains date-related keywords
                        if any(keyword in col_lower for keyword in date_column_keywords):
                            # For numeric columns that represent time (like year or age)
                            if any(indicator in col_lower for indicator in numeric_time_indicators):
                                if selected_df[col].dtype in ['int64', 'float64']:
                                    date_col = col
                                    # Convert numeric years to datetime
                                    try:
                                        # Check if values are within reasonable year range
                                        if selected_df[col].min() >= 1000 and selected_df[col].max() <= 3000:
                                            selected_df[col] = pd.to_datetime(selected_df[col], format='%Y')
                                        else:
                                            # Create date range based on index
                                            selected_df[col] = pd.date_range(
                                                start='2000-01-01',
                                                periods=len(selected_df),
                                                freq='D'
                                            )
                                    except Exception as e:
                                        # Fallback to date range if conversion fails
                                        selected_df[col] = pd.date_range(
                                            start='2000-01-01',
                                            periods=len(selected_df),
                                            freq='D'
                                        )
                                    break
                            else:
                                # Try converting to datetime for date-like columns
                                try:
                                    selected_df[col] = pd.to_datetime(selected_df[col], errors="coerce")
                                    if selected_df[col].notna().sum() > 0:
                                        date_col = col
                                        break
                                except Exception:
                                    continue
                    except Exception:
                        continue
                
                # If no date column found, check if any existing column could be a date
                if date_col is None:
                    for col in selected_df.columns:
                        try:
                            # Try to convert common date formats
                            selected_df[col] = pd.to_datetime(selected_df[col], errors="coerce")
                            if selected_df[col].notna().sum() > len(selected_df) * 0.5:  # At least 50% valid dates
                                date_col = col
                                break
                        except Exception:
                            continue
                
                # If still no date column found, look for numeric columns that could represent time series
                if date_col is None:
                    numeric_cols = selected_df.select_dtypes(include=[np.number]).columns
                    
                    # First check for columns that look like years
                    for col in numeric_cols:
                        values = selected_df[col].dropna().unique()
                        # Check if values look like years (between 1900 and 2100)
                        if len(values) > 0 and values.min() >= 1900 and values.max() <= 2100:
                            date_col = col
                            try:
                                selected_df[col] = pd.to_datetime(selected_df[col], format='%Y')
                                break
                            except Exception:
                                continue
                    
                    # If still no date found, look for any sequential numeric column
                    if date_col is None:
                        for col in numeric_cols:
                            # Check if the column is sorted or has regular intervals
                            if selected_df[col].is_monotonic_increasing:
                                date_col = col
                                try:
                                    # Create a datetime index with daily frequency
                                    selected_df[col] = pd.date_range(
                                        start='2000-01-01',
                                        periods=len(selected_df),
                                        freq='D'
                                    )
                                    break
                                except pd.errors.OutOfBoundsDatetime:
                                    # If dataset too large, use a smaller subset
                                    st.warning(f"Dataset too large to create date range. Using first 1000 rows.")
                                    selected_df = selected_df.head(1000)
                                    selected_df[col] = pd.date_range(
                                        start='2000-01-01',
                                        periods=len(selected_df),
                                        freq='D'
                                    )
                                    break
                
                # If all else fails, create a synthetic date column
                if date_col is None:
                    st.info("⚠ No suitable data found for forecasting")
                    selected_df['synthetic_date'] = pd.date_range(
                        start='2000-01-01',
                        periods=len(selected_df),
                        freq='D'
                    )
                    date_col = 'synthetic_date'
                
                # Now proceed with forecasting since we've ensured a date column exists
                numeric_columns = selected_df.select_dtypes(include=[np.number]).columns.tolist()
                if date_col in numeric_columns:
                    numeric_columns.remove(date_col)

                if not numeric_columns:
                    st.error("⚠ No suitable data found for forecasting")
                else:
                    target_col = st.selectbox(f"Select Target Column for `{selected_file}`:", numeric_columns)

                    # 📊 Forecasting Preparation
                    # Use the last available date from the dataset to start the forecasting
                    last_date = selected_df[date_col].max()
                    
                    # Ensure last_date is valid
                    try:
                        last_date = pd.to_datetime(last_date)
                        
                        # Generate future forecast index starting from the last available date
                        # Remove the slider and use a fixed value of 10 periods
                        forecast_periods = 10  # Fixed at 10 periods
                        forecast_freq = st.selectbox("Forecast frequency:", ["Y", "Q", "M", "W", "D"], index=0)
                        
                        forecast_index = pd.date_range(
                            start=last_date,
                            periods=forecast_periods,
                            freq=forecast_freq
                        )

                        # 🔥 Try Prophet Forecasting, Else Use Random Forest
                        forecast = None
                        try:
                            # Clean data for Prophet - remove NaNs and duplicates
                            prophet_df = pd.DataFrame({
                                'ds': selected_df[date_col],
                                'y': selected_df[target_col]
                            }).dropna()
                            
                            # Remove duplicate dates which can cause Prophet to fail
                            prophet_df = prophet_df.drop_duplicates(subset=['ds'])
                            
                            # Check if we have enough data points
                            if len(prophet_df) < 2:
                                raise ValueError("Not enough valid data points for forecasting")
                            
                            # Initialize and fit Prophet model with proper error handling
                            model = Prophet(yearly_seasonality=True)
                            model.fit(prophet_df)
                            
                            # Create future dates dataframe
                            future_periods = min(15, forecast_periods * 3)  # Use at least 15 periods for visualization
                            future = model.make_future_dataframe(periods=future_periods, freq=forecast_freq)
                            
                            # Make predictions
                            forecast = model.predict(future)
                            
                            # Visualization
                            fig = model.plot(forecast)
                            
                            # Customize the plot
                            ax = fig.gca()
                            ax.set_title(f"Forecast vs Actual Data for `{selected_file}`", size=14)
                            ax.set_xlabel("Date", size=12)
                            ax.set_ylabel(target_col, size=12)
                            ax.tick_params(axis="x", labelsize=10)
                            ax.tick_params(axis="y", labelsize=10)
                            
                            st.pyplot(fig)
                            
                            # Show the components plot
                            components_fig = model.plot_components(forecast)
                            st.write("### 📊 Forecast Components")
                            st.pyplot(components_fig)
                            
                        except Exception as e:
                            st.write(f"Prophet model failed: {str(e)}")
                            # st.write("Switching to Random Forest.")
                            try:
                                # Random Forest Forecasting
                                # Convert dates to numeric for Random Forest
                                min_date = pd.to_datetime(selected_df[date_col].min())
                                
                                # Create timestamp feature (days since min date)
                                selected_df["timestamp"] = (pd.to_datetime(selected_df[date_col]) - min_date).dt.days
                                
                                # Clean data
                                rf_data = selected_df[["timestamp", target_col]].dropna()
                                
                                if len(rf_data) < 2:
                                    raise ValueError("Not enough valid data points for forecasting")
                                
                                X = rf_data[["timestamp"]]
                                y = rf_data[target_col]

                                # Random Forest Model
                                model = RandomForestRegressor(n_estimators=150, random_state=42)
                                model.fit(X, y)

                                # Future Timestamps
                                future_days = [(pd.to_datetime(date) - min_date).days for date in forecast_index]
                                future_timestamps = np.array(future_days).reshape(-1, 1)
                                forecast_values = model.predict(future_timestamps)
                                
                                # Create plot
                                fig, ax = plt.subplots(figsize=(10, 6))
                                ax.scatter(rf_data["timestamp"], rf_data[target_col], label='Historical Data')
                                ax.plot(future_days, forecast_values, color='red', label='Forecast')
                                ax.set_title(f"Random Forest Forecast for {target_col}")
                                ax.set_xlabel("Days from start")
                                ax.set_ylabel(target_col)
                                ax.legend()
                                st.pyplot(fig)
                                
                                # Create a dataframe with the forecast results
                                forecast_df = pd.DataFrame({
                                    'Date': forecast_index,
                                    f'Forecast {target_col}': forecast_values
                                })
                                st.write("### 📊 Forecast Results")
                                st.dataframe(forecast_df)
                                
                                st.success("Random Forest model forecast successful!")
                            except Exception as e:
                                st.error(f"⚠ Not suitable data to forecast: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error preparing forecast: {str(e)}")

    # Show the chatbot only if files have been uploaded and user has not reached their limit
    if dataframes and not has_reached_limit:
        st.write("")
        if bedrock_client:
            chatbot_section(dataframes, file_names, bedrock_client)
        else:
            st.warning("⚠️ Amazon Bedrock client not initialized. AI assistant is unavailable.")
            st.info("To enable the AI assistant, install boto3 and configure AWS credentials.")
    elif not has_reached_limit:
        st.info("📤 Please upload a dataset above to enable the AI chat assistant.")
