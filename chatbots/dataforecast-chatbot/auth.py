import os
import streamlit as st
import json
import logging
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from streamlit_javascript import st_javascript
from db_storage import save_user_data
import time
from datetime import datetime, timedelta
import psycopg2

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a placeholder for the data directory (used by other modules)
DATA_DIR = os.path.join(os.path.expanduser("~"), "persistent_data")

# Default username for the application (no login required)
DEFAULT_USERNAME = "default_user"

# Get secret key from environment variables
SECRET_KEY = os.getenv("SECRET_KEY")

# Premium usage limit and subscription duration in seconds
PREMIUM_USAGE_LIMIT = 20
SUBSCRIPTION_DURATION_DAYS = 1  # 1 day subscription

# 🔑 User Authentication State
def init_session_state():
    # Set authenticated to False by default (changed from True to False)
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        logger.info("Initialized authenticated state to False")
    
    # Set default username if not already set
    if "user_name" not in st.session_state:
        st.session_state.user_name = DEFAULT_USERNAME
        logger.info(f"Initialized user_name to {DEFAULT_USERNAME}")
    
    # For backward compatibility
    if "username" not in st.session_state:
        st.session_state.username = st.session_state.user_name
    
    # Initialize usage count (resets on app restart)
    if "usage_count" not in st.session_state:
        st.session_state.usage_count = 0
    
    # Initialize premium usage count
    if "premium_usage_count" not in st.session_state:
        st.session_state.premium_usage_count = 0
    
    # Initialize subscription expiration timestamp
    if "subscription_expires_at" not in st.session_state:
        st.session_state.subscription_expires_at = None
    
    if "paid_user" not in st.session_state:
        st.session_state.paid_user = False
    
    # For backward compatibility
    if "premium_user" in st.session_state and st.session_state.premium_user:
        st.session_state.paid_user = True

# 🔐 Check Authentication with token
def check_auth():
    # Try getting token from localStorage
    token_js = st_javascript("await localStorage.getItem('user_token');", key="auth_get_token_js")
    name_js = st_javascript("await localStorage.getItem('user_name');", key="auth_get_name_js")
    
    logger.info(f"Auth check - Token found: {bool(token_js)}, Name found: {bool(name_js)}")
    
    if token_js:
        try:
            decoded = jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"])
            username = decoded.get("name", name_js or "Unknown User")
            email = decoded.get("email", "No Email")
            
            # Set basic user information
            st.session_state.user_name = username
            st.session_state.username = username  # For backward compatibility
            st.session_state.user_email = email
            st.session_state.authenticated = True
            
            logger.info(f"Token validated successfully for user: {username}")
            
            # Check if user has made payment by looking in database
            is_premium = check_premium_status_in_db(email=email, name=username)
            
            if is_premium:
                st.session_state.premium_user = True
                st.session_state.paid_user = True
                
                # Set subscription expiration if not already set
                if not st.session_state.subscription_expires_at:
                    set_subscription_expiration()
                    
                logger.info(f"Premium access granted to user: {username}")
            else:
                # Not a premium user
                st.session_state.premium_user = False
                st.session_state.paid_user = False
                logger.info(f"User authenticated with standard access: {username}")
            
            # Check if premium subscription has expired
            check_premium_subscription()
            return True
            
        except (ExpiredSignatureError, InvalidTokenError) as e:
            logger.warning(f"Token validation failed: {str(e)}")
            # Clear invalid token
            st_javascript("localStorage.removeItem('user_token');", key="auth_remove_token_js")
            st_javascript("localStorage.removeItem('user_name');", key="auth_remove_name_js")
            st.session_state.authenticated = False
            return False
    else:
        logger.info("No valid token found")
        st.session_state.authenticated = False
        return False

# Check if premium subscription has expired
def check_premium_subscription():
    if st.session_state.paid_user or st.session_state.get("premium_user", False):
        current_time = int(time.time())
        
        # Check expiration date
        if st.session_state.subscription_expires_at and current_time > int(st.session_state.subscription_expires_at):
            logger.info(f"Premium subscription expired for user: {st.session_state.username}")
            st.session_state.paid_user = False
            st.session_state.premium_user = False
        
        # Check usage limit
        elif st.session_state.premium_usage_count >= PREMIUM_USAGE_LIMIT:
            logger.info(f"Premium usage limit reached for user: {st.session_state.username}")
            st.session_state.paid_user = False
            st.session_state.premium_user = False

# 🔐 Sign Out Function
def sign_out():
    # Clear localStorage
    st_javascript("localStorage.removeItem('user_token');", key="signout_remove_token_js")
    st_javascript("localStorage.removeItem('user_name');", key="signout_remove_name_js")
    
    # Reset session state
    st.session_state.user_name = DEFAULT_USERNAME
    st.session_state.username = DEFAULT_USERNAME
    st.session_state.authenticated = False
    st.session_state.premium_user = False
    st.session_state.paid_user = False
    st.session_state.usage_count = 0
    st.session_state.premium_usage_count = 0
    st.session_state.subscription_expires_at = None
    
    # Set direct redirect flag
    st.session_state.direct_redirect = True
    
    logger.info("User signed out")
    st.rerun()

# 🔢 Track Usage Function
def increment_usage():
    # Increment the appropriate usage counter
    if st.session_state.paid_user or st.session_state.get("premium_user", False):
        st.session_state.premium_usage_count += 1
        logger.info(f"Premium usage count incremented: {st.session_state.premium_usage_count}")
    else:
        st.session_state.usage_count += 1
        logger.info(f"Usage count incremented: {st.session_state.usage_count}")
    
    # Save the updated usage count to the database
    update_user_in_db()

# 🛑 Check Usage Limits
def check_usage_limit():
    # First check if user is premium and if premium subscription is still valid
    check_premium_subscription()
    
    # If still premium after check, user has unlimited access
    if st.session_state.paid_user or st.session_state.get("premium_user", False):
        # Check if premium user has exceeded usage limit
        if st.session_state.premium_usage_count < PREMIUM_USAGE_LIMIT:
            return True
        else:
            return False
    
    # For non-premium users, check against free usage limit
    FREE_USAGE_LIMIT = 6
    if st.session_state.usage_count < FREE_USAGE_LIMIT:
        return True
    else:
        return False

# Get premium status info
def get_premium_status():
    current_time = int(time.time())
    premium_active = st.session_state.paid_user or st.session_state.get("premium_user", False)
    
    if not premium_active:
        return {
            "active": False,
            "message": "Free account"
        }
    
    # Calculate remaining time
    remaining_time = "Unknown"
    if st.session_state.subscription_expires_at:
        expiry_time = int(st.session_state.subscription_expires_at)
        if current_time < expiry_time:
            # Calculate days and hours remaining
            remaining_seconds = expiry_time - current_time
            days, remainder = divmod(remaining_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            
            if days > 0:
                remaining_time = f"{days} days, {hours} hours"
            else:
                remaining_time = f"{hours} hours"
    
    # Calculate remaining uses
    remaining_uses = PREMIUM_USAGE_LIMIT - st.session_state.premium_usage_count
    
    return {
        "active": True,
        "expires_in": remaining_time,
        "uses_remaining": remaining_uses,
        "max_uses": PREMIUM_USAGE_LIMIT
    }

# Save user data to database
def update_user_in_db():
    try:
        # Debug output
        print("=== DEBUG: update_user_in_db called ===")
        print(f"Username: {st.session_state.username}")
        print(f"Paid user: {st.session_state.paid_user}")
        print(f"Usage count: {st.session_state.usage_count}")
        print(f"Premium usage count: {st.session_state.premium_usage_count}")
        print(f"Subscription expires at: {st.session_state.subscription_expires_at}")
        
        # Create a dictionary with just the user data we want to store
        user_data = {
            st.session_state.username: {
                'password': 'none',  # Required field but not used for auth
                'email': getattr(st.session_state, 'email', ''),  # Save email if exists
                'paid_user': 1 if (st.session_state.paid_user or st.session_state.get("premium_user", False)) else 0,
                'usage_count': st.session_state.usage_count,  # Save current usage count
                'premium_usage_count': st.session_state.premium_usage_count,
                'subscription_expires_at': st.session_state.subscription_expires_at
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

# Set subscription expiration timestamp
def set_subscription_expiration():
    # Set expiration to current time + SUBSCRIPTION_DURATION_DAYS
    expiration_time = int(time.time()) + (SUBSCRIPTION_DURATION_DAYS * 24 * 60 * 60)
    st.session_state.subscription_expires_at = str(expiration_time)
    
    # Format for display
    expiration_date = datetime.fromtimestamp(expiration_time).strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"Set subscription expiration to: {expiration_date}")
    
    # Save to database
    update_user_in_db()
    
    return expiration_date

# Check if user has premium status in database
def check_premium_status_in_db(email=None, name=None):
    """
    Check if a user has premium status by verifying payment in the database
    Returns True if premium user found, False otherwise
    """
    try:
        # Only proceed if we have at least one identifier
        if not email and not name:
            logger.warning("Cannot check premium status without email or name")
            return False
            
        # Check for premium status in database
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        
        # Check the premium users table
        search_query = """
            SELECT * FROM bbt_premiumusers 
            WHERE 1=1
        """
        
        params = []
        
        # Add conditions based on available identifiers
        if email:
            search_query += " AND email = %s"
            params.append(email)
        
        if name:
            search_query += " AND name = %s"
            params.append(name)
            
        cursor.execute(search_query, params)
        result = cursor.fetchone()
        conn.close()
        
        # If we find a record, user has premium access
        if result:
            logger.info(f"Premium user found in database: {name or email}")
            return True
        else:
            logger.info(f"No premium record found for user: {name or email}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking premium status in database: {e}")
        return False

# Function to check if user is authenticated
def is_authenticated():
    """
    Check if the user is authenticated by examining the session state.
    Returns True if authenticated, False otherwise.
    """
    if "authenticated" in st.session_state and st.session_state.authenticated:
        logger.info("User is authenticated")
        return True
    
    # Try to authenticate from existing token
    authenticated = check_auth()
    logger.info(f"Authentication check result: {authenticated}")
    return authenticated

# Function to require authentication
def require_auth():
    """
    Force user to authenticate by redirecting to login page or showing login form.
    Returns True if the user is authenticated, False otherwise.
    """
    # First check if user is already authenticated
    if is_authenticated():
        logger.info("User is already authenticated")
        return True
    
    # If we get here, user is not authenticated
    logger.info("User is not authenticated, showing login form")
    
    # Clear any potentially expired/invalid tokens
    st_javascript("localStorage.removeItem('user_token');", key="require_auth_remove_token_js")
    st_javascript("localStorage.removeItem('user_name');", key="require_auth_remove_name_js")
    
    # Set flag to indicate authentication required
    st.session_state.auth_required = True
    
    # The main.py will handle showing the login form
    return False
