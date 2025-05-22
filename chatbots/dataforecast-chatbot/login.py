import streamlit as st
import time
import os
import jwt
from streamlit_javascript import st_javascript
import psycopg2
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get secret key from environment variables
SECRET_KEY = os.getenv("SECRET_KEY")

def login_page():
    st.set_page_config(page_title="Login - Data Analysis & Forecasting", page_icon="🔐")
    
    # Add custom CSS for centered title and styling
    st.markdown(
        """
        <style>
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            max-width: 400px;
            margin: 0 auto;
        }
        .login-title {
            text-align: center;
            font-size: 2.5rem;
            font-weight: bold;
            color: #17a7e0;
            margin-bottom: 2rem;
        }
        .login-form {
            width: 100%;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            background-color: white;
        }
        .login-button {
            width: 100%;
            margin-top: 1rem;
            background-color: #17a7e0;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Check if already authenticated via token
    if "check_token" not in st.session_state:
        token_js = st_javascript("await localStorage.getItem('user_token');", key="login_token_check_js")
        if token_js:
            try:
                # Validate token
                decoded = jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"])
                # Token is valid, redirect to main app
                st.markdown(
                    """
                    <script>
                    window.location.href = "/";
                    </script>
                    <meta http-equiv="refresh" content="0; url=/" />
                    """,
                    unsafe_allow_html=True
                )
                st.info("You are already logged in. Redirecting to the main app...")
                st.session_state.check_token = True
                st.stop()
            except:
                # Token is invalid, proceed with login
                pass
    
    # 📸 Add Logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.png", width=200)
    
    # Login form in a centered container
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h1 class='login-title'>Login</h1>", unsafe_allow_html=True)
    st.markdown("<div class='login-form'>", unsafe_allow_html=True)
    
    email = st.text_input("Email Address", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    
    login_button = st.button("Login", use_container_width=True, key="login_button")
    
    if login_button:
        if not email or not password:
            st.error("Please enter both email and password")
        else:
            # Implement authentication logic here
            try:
                # Connect to database
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    dbname=os.getenv("DB_NAME")
                )
                cursor = conn.cursor()
                
                # Query for the user
                query = "SELECT name FROM bbt_tempusers WHERE email = %s LIMIT 1"
                cursor.execute(query, (email,))
                result = cursor.fetchone()
                
                if result:
                    user_name = result[0]
                    
                    # Create a token
                    payload = {
                        "name": user_name,
                        "email": email,
                        "exp": int(time.time()) + 86400  # 24 hours
                    }
                    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
                    
                    # Store token in localStorage
                    st_javascript(f"localStorage.setItem('user_token', '{token}');", key="login_set_token_js")
                    st_javascript(f"localStorage.setItem('user_name', '{user_name}');", key="login_set_name_js")
                    
                    # Show success message
                    st.success("✅ Login successful!")
                    
                    # Redirect to main app
                    st.markdown(
                        """
                        <script>
                        setTimeout(function() {
                            window.location.href = "/";
                        }, 1000);
                        </script>
                        <meta http-equiv="refresh" content="1; url=/" />
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.error("❌ Invalid email or password")
                
                conn.close()
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                st.error(f"❌ Error during login: {str(e)}")
    
    st.markdown("</div>", unsafe_allow_html=True)  # Close login-form div
    
    # Register link
    st.markdown(
        """
        <div style="text-align: center; margin-top: 1rem;">
            <p>Don't have an account? <a href="https://www.bellblazetech.com/contact" target="_blank">Contact us</a></p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("</div>", unsafe_allow_html=True)  # Close login-container div

if __name__ == "__main__":
    login_page() 
