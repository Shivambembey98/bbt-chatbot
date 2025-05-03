import os
import streamlit as st
import json
import logging
from db_storage import save_user_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a placeholder for the data directory (used by other modules)
DATA_DIR = os.path.join(os.path.expanduser("~"), "persistent_data")

# Default username for the application (no login required)
DEFAULT_USERNAME = "default_user"

# 🔑 User Authentication State
def init_session_state():
    # Set authenticated to True by default
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = True
    
    # Set default username
    if "username" not in st.session_state:
        st.session_state.username = DEFAULT_USERNAME
    
    # Initialize usage count (resets on app restart)
    if "usage_count" not in st.session_state:
        st.session_state.usage_count = 0
    
    if "paid_user" not in st.session_state:
        st.session_state.paid_user = False  # Set to False to enable limits

# 🔐 Check Authentication (now just a pass-through)
def check_auth():
    # Always proceed - no checks needed
    pass

# 🔐 Sign Out Function (kept for compatibility)
def sign_out():
    # Just reset to default state
    st.session_state.username = DEFAULT_USERNAME
    st.session_state.usage_count = 0
    st.rerun()

# 🔢 Track Usage Function (simplified, no persistence)
def increment_usage():
    # Just increment the usage count in session
    st.session_state.usage_count += 1
    logger.info(f"Usage count incremented: {st.session_state.usage_count}")
    
    # Save the updated usage count to the database
    update_user_in_db()

# 🛑 Check Usage Limits (limits to 6 uses, unless premium)
def check_usage_limit():
    # Free usage limit
    FREE_USAGE_LIMIT = 6
    
    # Premium users have unlimited access
    if st.session_state.paid_user:
        return True
    
    # Check if user has reached usage limit
    if st.session_state.usage_count < FREE_USAGE_LIMIT:
        return True
    else:
        return False

# Save user data to database
def update_user_in_db():
    try:
        # Debug output
        print("=== DEBUG: update_user_in_db called ===")
        print(f"Username: {st.session_state.username}")
        print(f"Paid user: {st.session_state.paid_user}")
        print(f"Usage count: {st.session_state.usage_count}")
        
        # Create a dictionary with just the user data we want to store
        user_data = {
            st.session_state.username: {
                'password': 'none',  # Required field but not used for auth
                'email': getattr(st.session_state, 'email', ''),  # Save email if exists
                'paid_user': 1 if st.session_state.paid_user else 0,  # Convert boolean to integer
                'usage_count': st.session_state.usage_count  # Save current usage count
            }
        }
        
        print(f"User data to save: {user_data}")
        
        # Save to database
        success = save_user_data(user_data)
        if success:
            print("User data saved to database successfully")
            logger.info(f"User data for {st.session_state.username} saved to database successfully")
        else:
            print("Failed to save user data to database")
            logger.warning(f"Failed to save user data for {st.session_state.username} to database")
    except Exception as e:
        print(f"Error saving user data to database: {e}")
        logger.error(f"Error saving user data to database: {e}")
