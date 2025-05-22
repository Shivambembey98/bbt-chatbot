import streamlit as st
import sys
import os
import logging
from auth import is_authenticated, require_auth


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This script can be imported at the beginning of any Streamlit page
# to automatically enforce authentication

def enforce_auth():
    """
    Enforce authentication for any page that imports this middleware.
    If the user is not authenticated, they will be redirected to the login page.
    """
    # Skip auth check for login.py itself to avoid redirect loops
    current_script = sys.argv[0] if len(sys.argv) > 0 else ""
    script_name = os.path.basename(current_script)
    
    logger.info(f"Middleware checking auth for script: {script_name}")
    
    # Skip auth check for login page
    if script_name == "login.py":
        logger.info("Skipping auth check for login page")
        return
    
    # If there's an auth check in progress, avoid a loop
    if "auth_check_in_progress" in st.session_state and st.session_state.auth_check_in_progress:
        logger.info("Auth check already in progress, skipping to avoid loops")
        return
    
    # Set flag to prevent loops
    st.session_state.auth_check_in_progress = True
    
    # Check authentication and redirect if not authenticated
    auth_status = is_authenticated()
    logger.info(f"Auth status: {auth_status}")
    
    if not auth_status:
        logger.info("User not authenticated, redirecting to login")
        require_auth()
        st.stop()
    
    # Clear flag
    st.session_state.auth_check_in_progress = False
    logger.info("Auth check completed successfully")

# Run auth check when this script is imported
try:
    enforce_auth()
except Exception as e:
    logger.error(f"Error in middleware: {e}")
    # Don't stop the app if middleware fails
    pass 
