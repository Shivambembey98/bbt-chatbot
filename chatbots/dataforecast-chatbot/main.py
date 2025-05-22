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
import psycopg2
from dotenv import load_dotenv
from statsmodels.tsa.arima.model import ARIMA
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from auth import init_session_state, check_auth, sign_out, increment_usage, check_usage_limit, DATA_DIR, update_user_in_db, set_subscription_expiration, get_premium_status, require_auth
from chatbot import chatbot_section  
from prophet import Prophet
from plotly import graph_objs as go
from db_storage import save_forecast, load_forecast, save_chat_history, load_chat_history, save_transaction
from razorpay_payment import RazorpayPayment, display_payment_interface
from streamlit_javascript import st_javascript
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import boto3
import psycopg2
import streamlit.components.v1 as components


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Very first execution - check for token=None in URL and clean before anything else
if "token" in st.query_params and st.query_params.get("token") == "None":
    logger.info("Detected token=None in early URL check, forcefully cleaning URL")
    
    # Use the most direct method for cleaning immediately
    st.markdown(
        """
        <script>
        // Immediately clean URL (multiple approaches for redundancy)
        window.location.href = window.location.pathname; 
        window.location.replace(window.location.pathname);
        window.history.replaceState({}, document.title, window.location.pathname);
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Also try Streamlit's methods
    st.query_params.clear()
    
    # Stop execution completely - forcing a clean URL
    st.stop()

# Load environment variables early to get SECRET_KEY 
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")

# Initialize session state early
init_session_state()

def login_form():
    """Display a login button that redirects to the Bell Blaze external authentication system."""
    st.title("🔐 Please Login to Continue")
    
    st.markdown("<div style='text-align: center; margin: 30px 0;'>", unsafe_allow_html=True)
    st.markdown("### Please log in to access the AI-Powered Data Analysis and Forecasting tool")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Create a centered container for the login button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Add a clean URL for the return path (without any token)
        app_url = "/dataforecast-chatbot"
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin: 30px 0;">
                <a href="http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/login?DomainPath={app_url}" target="_self">
                    <button style="
                        background-color: #17a7e0;
                        color: white;
                        border: none;
                        padding: 15px 32px;
                        text-align: center;
                        text-decoration: none;
                        display: inline-block;
                        font-size: 16px;
                        margin: 4px 2px;
                        cursor: pointer;
                        border-radius: 8px;
                        font-weight: bold;
                        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    ">
                        Log In with Bell Blaze
                    </button>
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Additional explanation
    st.markdown(
        """
        <div style="text-align: center; color: #555; margin-top: 20px;">
            <p>You will be redirected to the Bell Blaze authentication system.</p>
            <p>After logging in, you will be returned to this application automatically.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    return False

# Add immediate handling for payment success URL before any other processing
if "payment" in st.query_params and st.query_params.get("payment") == "success" and "transaction_id" in st.query_params:
    logger.info("Detected payment success in URL, processing payment first")
    
    # Get payment parameters
    payment_success = st.query_params.get("payment", "")
    txn_id = st.query_params.get("transaction_id", "")
    name = st.query_params.get("name", "")
    email = st.query_params.get("email", "")
    phone = st.query_params.get("phone", "")
    app_id = st.query_params.get("app_id", "dataforecast-chatbot")
    order_id = txn_id
    
    # Only process if we haven't already processed this payment
    if "payment_processed" not in st.session_state or not st.session_state.payment_processed:
        logger.info(f"Processing payment success at beginning: txn_id={txn_id}, name={name}, email={email}")
        
        # Clean URL immediately before processing anything else
        st.markdown(
            """
            <script>
            (function cleanURLImmediately() {
                const cleanPath = window.location.pathname;
                window.history.replaceState({}, document.title, cleanPath);
                window.location.replace(cleanPath);
            })();
            </script>
            """,
            unsafe_allow_html=True
        )
        
        # Set session state values
        st.session_state.user_name = name
        st.session_state.premium_user = True
        st.session_state.payment_processed = True
        st.session_state.authenticated = True
        
        # Show success message with immediate display
        st.balloons()
        st.success("✅ Payment successful! Premium features unlocked!")
        
        # Clean URL programmatically
        st.query_params.clear()
        
        # Try to save to database with retries and better error handling
        max_retries = 3
        retry_delay = 1  # seconds
        conn = None
        success = False
        
        for attempt in range(max_retries):
            try:
                # Log connection attempt
                logger.info(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
                
                # Create connection
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    dbname=os.getenv("DB_NAME"),
                    connect_timeout=10  # Increased timeout
                )
                
                # Log connection success
                logger.info("Database connection established successfully")
                
                cursor = conn.cursor()
                
                # First, check if the table exists
                check_table_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'bbt_tempusers'
                    );
                """
                cursor.execute(check_table_query)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    # Create the table if it doesn't exist
                    create_table_query = """
                        CREATE TABLE IF NOT EXISTS bbt_tempusers (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            email VARCHAR(255) NOT NULL,
                            phone VARCHAR(20),
                            app_id VARCHAR(100),
                            order_id VARCHAR(100) UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """
                    cursor.execute(create_table_query)
                    conn.commit()
                    logger.info("Created bbt_tempusers table")
                
                # Check if record already exists
                check_query = """
                    SELECT id FROM bbt_tempusers 
                    WHERE order_id = %s
                    LIMIT 1;
                """
                cursor.execute(check_query, (order_id,))
                existing_record = cursor.fetchone()
                
                if existing_record:
                    logger.info(f"Payment record already exists for order_id: {order_id}")
                    success = True
                else:
                    # Insert new record with all fields explicitly listed
                    insert_query = """
                        INSERT INTO bbt_tempusers (name, email, phone, app_id, order_id, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        RETURNING id;
                    """
                    cursor.execute(insert_query, (name, email, phone, app_id, order_id))
                    inserted_id = cursor.fetchone()[0]
                    conn.commit()
                    logger.info(f"Payment record saved successfully with ID: {inserted_id}")
                    success = True
                
                break  # Exit retry loop if successful
                
            except psycopg2.OperationalError as e:
                logger.error(f"Database connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("All database connection attempts failed")
                    
            except psycopg2.IntegrityError as e:
                logger.error(f"Database integrity error: {str(e)}")
                if "duplicate key value violates unique constraint" in str(e):
                    logger.info(f"Payment record already exists for order_id: {order_id}")
                    success = True  # Consider it a success if the record already exists
                    break
                    
            except Exception as e:
                logger.error(f"Unexpected error saving to database: {str(e)}")
                if conn:
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.error(f"Error during rollback: {str(rollback_error)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    
            finally:
                if conn:
                    try:
                        conn.close()
                        logger.info("Database connection closed")
                    except Exception as close_error:
                        logger.error(f"Error closing database connection: {str(close_error)}")
        
        if not success:
            logger.error("Failed to save payment record after all retries")
            
        # Very brief pause to ensure success message is seen
        time.sleep(0.2)
        
        # Rerun app with clean URL immediately
        logger.info("Payment processed successfully, rerunning with clean URL")
        st.rerun()

# Add immediate handling for token=None URL before any other processing
if "token" in st.query_params and st.query_params.get("token") == "None":
    logger.info("Detected token=None in URL, forcefully cleaning URL")
    # Direct URL cleaning with immediate redirect
    st.markdown(
        """
        <script>
        // Immediately redirect to clean path using multiple methods
        window.history.replaceState({}, document.title, window.location.pathname);
        window.location.replace(window.location.pathname);
        
        // As a fallback, use hard redirect after a tiny delay
        setTimeout(function() {
            if (window.location.search) {
                window.location.href = window.location.pathname;
            }
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Also try programmatic clearing
    st.query_params.clear()
    
    # Stop execution to ensure redirect happens
    st.stop()

# Add a special handling for direct clear-token redirects
if "clear_token_redirect" in st.query_params:
    # We're in the redirect, clear all query params and show the app
    logger.info("In clean URL redirect flow")
    # Just in case, make sure we're authenticated
    st.session_state.authenticated = True
    
    # Force clear all query parameters
    st.markdown(
        """
        <script>
        // Force a clean URL without any parameters
        window.history.replaceState({}, document.title, window.location.pathname);
        // As a backup, also try with the window.location.href approach
        window.location.href = window.location.pathname;
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Also remove the clear_token_redirect flag from query params
    st.query_params.clear()
    
    # Continue with the app
    pass
elif "token" in st.query_params and "token_saved" not in st.session_state:
    # We have a token and haven't saved it yet, do that first
    token = st.query_params.get("token", "")
    logger.info("Token found in URL, handling with direct method")
    
    try:
        # Try to decode and validate the token
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        name = decoded.get("name", "Unknown User")
        
        # Store token in localStorage for future use
        st_javascript(f"localStorage.setItem('user_token', '{token}');", key="direct_set_token_js")
        st_javascript(f"localStorage.setItem('user_name', '{name}');", key="direct_set_name_js")
        
        # Set session state for the validated user
        st.session_state.user_name = name
        st.session_state.user_email = decoded.get("email", "No Email")
        st.session_state.authenticated = True
        st.session_state.token_saved = True
        
        logger.info(f"Token validated for user: {name}, redirecting to clean URL")
        
        # Force a clean redirect to the app without any parameters
        st.markdown(
            """
            <script>
            // Redirect to a completely clean URL
            window.location.href = window.location.pathname;
            </script>
            """,
            unsafe_allow_html=True
        )
        
        st.success(f"Welcome, {name}! Redirecting...")
        time.sleep(0.5)  # Brief pause to ensure message is shown
        st.rerun()  # Use rerun instead of stop to refresh the app
    except (ExpiredSignatureError, InvalidTokenError) as e:
        # Invalid token, ignore it and let the normal flow handle it
        logger.warning(f"Invalid token in direct handling: {e}")
        # Force clean the URL
        st.markdown(
            """
            <script>
            // Redirect to a completely clean URL
            window.location.href = window.location.pathname;
            </script>
            """,
            unsafe_allow_html=True
        )
        st.error("Invalid or expired token. Please log in again.")
        st.rerun()  # Use rerun instead of stop

# Always clear token from URL immediately at the top of the script
if "token" in st.query_params:
    # Log the token cleaning attempt
    logger.info(f"Cleaning token from URL: {st.query_params.get('token')}")
    
    # Add JavaScript to clear token from URL - using more forceful methods
    st.markdown(
        """
        <script>
        // Clear all parameters from URL with multiple methods for maximum compatibility
        // Method 1: Using replaceState (non-reloading)
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // Method 2: Direct URL redirect (most reliable but causes page reload)
        // Execute immediately if token=None is detected
        if (window.location.search.includes('token=None')) {
            window.location.href = window.location.pathname;
        } else {
            // Only execute if we still have parameters after 300ms (giving method 1 time to work)
            setTimeout(function() {
                if (window.location.search) {
                    window.location.href = window.location.pathname;
                }
            }, 300);
        }
        
        // Method 3: Use location.replace as a backup (no history entry)
        setTimeout(function() {
            if (window.location.search) {
                window.location.replace(window.location.pathname);
            }
        }, 600);
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Use meta refresh as a backup for browsers with JavaScript disabled
    st.markdown(
        f"""
        <noscript>
        <meta http-equiv="refresh" content="0;url={st.query_params.get('_stcore_url', '/dataforecast-chatbot').split('?')[0]}" />
        </noscript>
        """,
        unsafe_allow_html=True
    )
    
    # Also try to modify query_params directly
    if "token_processed" not in st.session_state:
        # Clear token parameter
        st.query_params["token"] = None
        # Try to clear all parameters
        try:
            st.query_params.clear()
        except:
            pass

# Check for direct redirect flag (immediate redirect to Bell Blaze Tech)
if 'direct_redirect' in st.session_state and st.session_state.direct_redirect:
    # Clear the flag
    st.session_state.direct_redirect = False
    logger.info("Redirecting to Bell Blaze Tech (direct_redirect flag set)")
    
    # Add a Javascript redirect, a meta refresh, and an HTML anchor with auto-click
    st.markdown(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/our-solutions">
        </head>
        <body>
            <a id="redirect-link" href="https://www.bellblazetech.com/our-solutions" style="display:none;">Redirect</a>
            <script type="text/javascript">
                window.top.location.href = "https://www.bellblazetech.com/our-solutions";
                document.getElementById('redirect-link').click();
            </script>
            <p>Redirecting to Bell Blaze Tech...</p>
        </body>
        </html>
        """,
        unsafe_allow_html=True
    )
    
    # Fallback text in case HTML doesn't render
    st.write("If you are not redirected automatically, please [click here](https://www.bellblazetech.com/our-solutions).")
    st.stop()

# Display sign-out page if needed
if 'show_signout_page' in st.session_state and st.session_state.show_signout_page:
    st.session_state.show_signout_page = False
    logger.info("Showing sign-out page")
    
    st.set_page_config(page_title="Signed Out")
    
    # Center content
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("You have been signed out")
        st.write("Thank you for using our application!")
        
        # Direct link button
        st.markdown(
            """
            <div style="text-align: center; margin-top: 30px;">
                <a href="https://www.bellblazetech.com/our-solutions" target="_self">
                    <button style="
                        background-color: #17a7e0;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        text-align: center;
                        text-decoration: none;
                        display: inline-block;
                        font-size: 16px;
                        margin: 4px 2px;
                        cursor: pointer;
                        border-radius: 4px;
                    ">
                        Continue to Bell Blaze Tech
                    </button>
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Add JavaScript redirect with delay
        st.markdown(
            """
            <script>
            setTimeout(function() {
                window.top.location.href = 'https://www.bellblazetech.com/our-solutions';
            }, 3000);
            </script>
            """,
            unsafe_allow_html=True
        )
    
    st.stop()

# Check if redirect flag is set
if 'redirect_to_bellblaze' in st.session_state and st.session_state.redirect_to_bellblaze:
    # Clear the flag
    st.session_state.redirect_to_bellblaze = False
    logger.info("Redirecting to Bell Blaze Tech (redirect_to_bellblaze flag set)")
    
    # Perform the redirect
    st.markdown(
        """
        <script language="javascript">
        window.top.location.href = "https://www.bellblazetech.com/our-solutions";
        </script>
        """,
        unsafe_allow_html=True
    )
    # Also add a meta tag for browsers that block scripts
    st.markdown(
        """
        <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/our-solutions" />
        """,
        unsafe_allow_html=True
    )
    st.write("Redirecting to Bell Blaze Tech website...")
    st.stop()

query_params = st.query_params
token = query_params.get("token", "")

# Create a session variable to store token if it's present in URL
if token and "url_token" not in st.session_state:
    st.session_state.url_token = token
elif "url_token" in st.session_state and not token:
    # If token was removed from URL but we stored it, use the stored one
    token = st.session_state.url_token
    # Only use it once
    del st.session_state.url_token

# Skip token processing if we've already processed it in this session
if "token_processed" in st.session_state and st.session_state.token_processed and token:
    # If we already processed a token, just make sure URL is clean
    token = ""  # Clear the token to avoid reprocessing

# Payment success parameters
payment_success = query_params.get("payment", "")
txn_id = query_params.get("transaction_id", "")
name = query_params.get("name", "")
email = query_params.get("email", "")
phone = query_params.get("phone", "")
app_id = st.query_params.get("app_id", "dataforecast-chatbot")
order_id = txn_id
# Initialize payment processed flag
if "payment_processed" not in st.session_state:
    st.session_state.payment_processed = False

# Handle payment success redirect
if payment_success == "success" and txn_id and not st.session_state.payment_processed:
    logger.info(f"Processing payment success: txn_id={txn_id}, name={name}, email={email}")
    
    # Store payment data in session state before cleaning URL
    st.session_state.user_name = name
    st.session_state.premium_user = True
    st.session_state.payment_processed = True
    st.session_state.authenticated = True
    
    # Clean URL using relative path approach
    st.markdown(
        """
        <script>
        (function cleanURL() {
            try {
                // Get the base path from the current URL
                const currentPath = window.location.pathname;
                const basePath = currentPath.endsWith('/') ? currentPath : currentPath + '/';
                
                // Clean the URL using relative path
                const cleanUrl = new URL(basePath, window.location.origin);
                window.history.replaceState({}, document.title, cleanUrl.pathname);
                
                // Fallback: if the above fails, try simple parameter removal
                if (window.location.search) {
                    window.location.search = '';
                }
            } catch (e) {
                console.log('URL cleaning fallback activated');
                // Final fallback: just remove search params
                if (window.location.search) {
                    window.location.search = '';
                }
            }
        })();
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Show success message after URL is cleaned
    st.balloons() 
    st.success("✅ Payment successful! Premium features unlocked!")
    
    # Let the success message and animations show briefly
    time.sleep(0.5)
    
    # Try to save to database with more detailed error handling
    conn = None
    try:
        # Log all environment variables (without sensitive info)
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        logger.info(f"Attempting database connection to {db_host}/{db_name} as {db_user}")
        
        # Try connection with explicit parameters
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=os.getenv("DB_PASSWORD"),
            port=5432,  # Add explicit port
            connect_timeout=10  # Increased timeout
        )
        
        # Set autocommit to false for transaction control
        conn.autocommit = False
        
        cursor = conn.cursor()
        
        # First ensure the table exists
        create_table_query = """
            CREATE TABLE IF NOT EXISTS bbt_tempusers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                app_id VARCHAR(100),
                order_id VARCHAR(100) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'active'
            );
        """
        cursor.execute(create_table_query)
        
        # Check if record already exists
        check_query = "SELECT id FROM bbt_tempusers WHERE order_id = %s"
        cursor.execute(check_query, (order_id,))
        exists = cursor.fetchone()
        
        if exists:
            logger.info(f"Payment record already exists for order_id: {order_id}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO bbt_tempusers(name, email, phone, app_id, order_id, created_at, status)
                VALUES (%s, %s, %s, %s, %s, NOW(), 'active')
                RETURNING id;
            """
            cursor.execute(insert_query, (name, email, phone, app_id, order_id))
            new_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"✅ Payment record saved successfully with ID: {new_id}")
            st.session_state["last_payment_id"] = new_id
            
    except psycopg2.OperationalError as e:
        logger.error(f"❌ Database connection error: {str(e)}")
        if 'connection refused' in str(e).lower():
            logger.error("Database server may be down or connection details incorrect")
        elif 'password authentication failed' in str(e).lower():
            logger.error("Database credentials are incorrect")
        if conn:
            conn.rollback()
            
    except psycopg2.IntegrityError as e:
        logger.error(f"❌ Database integrity error: {str(e)}")
        if 'duplicate key value' in str(e).lower():
            logger.info(f"Payment record already exists for order_id: {order_id}")
        if conn:
            conn.rollback()
            
    except Exception as e:
        logger.error(f"❌ Unexpected database error: {str(e)}")
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {str(rollback_error)}")
                
    finally:
        if conn:
            try:
                conn.close()
                logger.info("Database connection closed successfully")
            except Exception as close_error:
                logger.error(f"Error closing database connection: {str(close_error)}")
                
        # Log all relevant information for debugging
        logger.info(f"Payment processing completed for order_id: {order_id}")
        logger.info(f"User: {name}, Email: {email}, App: {app_id}")
    
    # Programmatically clear URL parameters
    st.query_params.clear()
    
    logger.info("Payment processed successfully, rerunning app with clean URL")
    st.rerun()  # Rerun the app with clean URL and premium features enabled

# Check authenticated status and show login form if needed
if not st.session_state.get("authenticated", False):
    # Process token from URL parameters first
    if token:
        logger.info("Token found in URL parameters, processing")
        try:
            # Store token and name in localStorage
            st_javascript(f"localStorage.setItem('user_token', '{token}');", key="main_set_token_js")
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            name = decoded.get("name", "Unknown User")
            st_javascript(f"localStorage.setItem('user_name', '{name}');", key="main_set_name_js")
     
            # Set session state for basic user info
            st.session_state.user_name = name
            st.session_state.user_email = decoded.get("email", "No Email")
            st.session_state.authenticated = True
            logger.info(f"Token validated for user: {name}")
            
            st.markdown(
                """
                <script>
                (function cleanURL() {
                    try {
                        const currentPath = window.location.pathname;
                        const basePath = currentPath.endsWith('/') ? currentPath : currentPath + '/';
                        window.history.replaceState({}, document.title, basePath);
                    } catch (e) {
                        console.log('URL cleaning fallback activated');
                        if (window.location.search) {
                            window.location.search = '';
                        }
                    }
                })();
                </script>
                """,
                unsafe_allow_html=True
            )
            
            # Add a flag to prevent rerunning code on next load
            if "token_processed" not in st.session_state:
                st.session_state.token_processed = True
                
                # Clear all query parameters from URL
                st.query_params.clear()
                # Adding a small delay before rerun
                time.sleep(0.2)
                st.rerun()  # Rerun the app to clear the URL
                
        except ExpiredSignatureError:
            logger.error("Session expired, token invalid")
            st.error("Session expired. Please login again.")
            st.session_state.authenticated = False
            
            # Clear the invalid token from URL with direct navigation
            st.markdown(
                """
                <script>
                // Force complete URL clean for invalid token
                window.location.href = window.location.pathname;
                </script>
                """,
                unsafe_allow_html=True
            )
        except InvalidTokenError:
            logger.error("Invalid token")
            st.error("Invalid token. Please login again.")
            st.session_state.authenticated = False
            
            # Clear the invalid token from URL with direct navigation
            st.markdown(
                """
                <script>
                // Force complete URL clean for invalid token
                window.location.href = window.location.pathname;
                </script>
                """,
                unsafe_allow_html=True
            )
    else:
        # Try to get token from localStorage
        token_js = st_javascript("await localStorage.getItem('user_token');", key="main_get_token_js")
        name_js = st_javascript("await localStorage.getItem('user_name');", key="main_get_name_js")
        
        # Validate token if present
        if token_js:
            try:
                decoded = jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"])
                username = decoded.get("name", name_js or "Unknown User")
                email = decoded.get("email", "No Email")
                
                # Set basic user information
                st.session_state.user_name = username
                st.session_state.username = username
                st.session_state.user_email = email
                st.session_state.authenticated = True
                logger.info(f"Token from localStorage validated for user: {username}")
            except (ExpiredSignatureError, InvalidTokenError) as e:
                logger.warning(f"Token validation failed: {str(e)}")
                # Clear invalid token from localStorage
                st_javascript("localStorage.removeItem('user_token');", key="main_clear_token_js")
                st_javascript("localStorage.removeItem('user_name');", key="main_clear_name_js")
                st.session_state.authenticated = False
        elif name_js:
            logger.info(f"Name found in localStorage but no valid token: {name_js}")
            st.session_state.authenticated = False

    # If still not authenticated after token checks, show login form
    if not st.session_state.get("authenticated", False):
        logger.info("User not authenticated, showing login form")
        login_form()
        st.stop()

# If we get here, the user is authenticated
logger.info(f"User authenticated: {st.session_state.user_name}")

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

# Initialize required session keys
required_session_keys = {
    "user_name": st.session_state.get("user_name", "Guest"),
    "premium_user": False,
    "chat_history": [],
}

for key, default_value in required_session_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# 🔐 Check Authentication - require authentication for access
logger.info("Checking authentication...")
if not require_auth():
    logger.info("Authentication failed, stopping execution")
    st.stop()  # Stop execution if authentication fails

logger.info("Authentication successful, continuing with app")

# 📍 AWS Bedrock Client Initialization
def get_bedrock_client():
    try:
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
    Maximum file size: 5MB
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
if st.session_state.paid_user or st.session_state.get("premium_user", False):
    # Get premium status info
    premium_status = get_premium_status()
    
    if premium_status["active"]:
        st.sidebar.success(f"💎 Premium Active")
        # st.sidebar.info(f"⏱️ Time Remaining: {premium_status['expires_in']}")
        st.sidebar.info(f"🔄 Uses Remaining: {premium_status['uses_remaining']}/{premium_status['max_uses']}")
    else:
        # Premium flag is set but status check shows it's expired/used up
        st.sidebar.warning("⚠️ Premium access expired. You've used all 20 available uses or your subscription period has ended.")
else:
    if remaining_uses > 0:
        st.sidebar.info(f"🔄 {remaining_uses} free uses remaining")
    else:
        st.sidebar.warning("⚠️ Free usage limit reached")

# Show welcome message with user's name
st.sidebar.markdown(f"### Welcome, {st.session_state.user_name}! 👋")

# Add Sign-Out Button in the sidebar (moved before Premium button)
if st.sidebar.button("Sign Out", use_container_width=True):
    sign_out()

# Function to toggle payment page
def toggle_payment_page():
    st.session_state.show_payment_page = not st.session_state.show_payment_page
    
    # If opening payment page, set a flag to track where the user came from
    if st.session_state.show_payment_page:
        # Store current app state to restore after payment
        if 'return_from_payment' not in st.session_state:
            st.session_state.return_from_payment = False

st.sidebar.markdown("### 💎 Upgrade to Premium")
if st.sidebar.button("💳 Upgrade to Premium", use_container_width=True):
    js = """
        <script>
        const token = localStorage.getItem('user_token');
        if (!token) {
            alert("No token found—please log in again.");
        } else {
            const params = new URLSearchParams({
            app_id: "dataforecast-chatbot",
            token: token
            });
            window.open(
            "https://paymentdocumentchatbot.s3.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html?" + params.toString(),
            "_blank"
            );
        }
        </script>
    """
    components.html(js, height=0, scrolling=False)
    

# 📚 Load Uploaded Files
dataframes = []
file_names = []

# Check if user has reached their usage limit before showing the uploader
has_reached_limit = not check_usage_limit()

# Only show file uploader if user has not reached their limit
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
        valid_files = []  # Store files that pass size validation
        
        # First validate all files
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            file_size = len(uploaded_file.getvalue())  # Get file size in bytes
            
            # 📏 Check File Size (Limit: 5MB)
            if file_size > 5 * 1024 * 1024:  # 5MB limit
                st.sidebar.error(f"❌ {file_name} exceeds 5MB size limit and will not be processed.")
            else:
                valid_files.append(uploaded_file)
        
        # Process only valid files
        for i, uploaded_file in enumerate(valid_files):
            file_name = uploaded_file.name
            file_size = len(uploaded_file.getvalue())
            
            # Check if this is a new file we haven't tracked yet
            file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
            file_identifier = f"{file_name}_{file_hash}"
            
            # If this is a new file, count it as usage
            if file_identifier not in st.session_state.tracked_files:
                st.session_state.tracked_files.add(file_identifier)
                increment_usage()
                
                # Check if user just hit their limit with this new upload
                if not check_usage_limit():
                    if st.session_state.paid_user or st.session_state.get("premium_user", False):
                        st.warning("⚠️ You've reached your premium usage limit (20 uses). Please renew your subscription to continue using the application.")
                    else:
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
    # If user has reached the limit, show the appropriate upgrade/renewal message
    if st.session_state.paid_user or st.session_state.get("premium_user", False):
        st.warning("⚠️ You've reached your premium usage limit (20 uses). Please renew your subscription to continue using the application.")
    else:
        st.warning("⚠️ You've reached your free usage limit (6 uses). Please upgrade to continue using the application.")
    
    # Clear any loaded dataframes and filenames to prevent access
    dataframes = []
    file_names = []
    
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
                if not check_usage_limit():
                    if st.session_state.paid_user or st.session_state.get("premium_user", False):
                        st.warning("⚠️ You've reached your premium usage limit (20 uses). Please renew your subscription to continue using the application.")
                    else:
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
