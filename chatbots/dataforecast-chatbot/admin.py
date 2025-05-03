import os
import streamlit as st
import json
import pandas as pd
from auth import DATA_DIR, load_users, save_users

# Admin Panel Password
ADMIN_PASSWORD = "admin123"  # Change this to a secure password

def admin_panel():
    st.title("🔐 Admin Panel")
    
    # Admin authentication
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        admin_password = st.text_input("Enter Admin Password", type="password")
        if st.button("Login"):
            if admin_password == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.success("✅ Admin authenticated successfully!")
                st.rerun()
            else:
                st.error("❌ Incorrect admin password")
        return
    
    # Admin is authenticated
    st.success("👤 Admin Mode Active")
    
    # Show data directory information
    st.subheader("📂 Data Storage Information")
    user_data_file = os.path.join(DATA_DIR, "users.json")
    chat_history_dir = os.path.join(DATA_DIR, "chat_history")
    
    st.info(f"Data directory: {DATA_DIR}")
    st.info(f"User data file: {user_data_file}")
    st.info(f"Chat history: {chat_history_dir}")
    
    # Check if files exist
    if os.path.exists(user_data_file):
        st.success(f"✅ User data file exists")
    else:
        st.error(f"❌ User data file not found")
    
    if os.path.exists(chat_history_dir):
        st.success(f"✅ Chat history directory exists")
    else:
        st.error(f"❌ Chat history directory not found")
    
    # Load and display user data
    st.subheader("👥 User Management")
    
    try:
        users = load_users()
        if not users:
            st.warning("No users found in the database")
        else:
            # Convert user data to DataFrame for better display
            user_rows = []
            for username, user_data in users.items():
                # Handle both old and new format users
                if isinstance(user_data, str):
                    # Old format (just password hash)
                    user_rows.append({
                        "Username": username,
                        "Paid User": "No",
                        "Usage Count": 0,
                        "Format": "Legacy"
                    })
                else:
                    # New format with usage tracking
                    user_rows.append({
                        "Username": username,
                        "Paid User": "Yes" if user_data.get("paid_user", False) else "No",
                        "Usage Count": user_data.get("usage_count", 0),
                        "Format": "Current"
                    })
            
            # Create and display DataFrame
            user_df = pd.DataFrame(user_rows)
            st.dataframe(user_df)
            
            # User actions section
            st.subheader("🛠️ User Actions")
            
            # Make a user premium
            col1, col2 = st.columns(2)
            
            with col1:
                selected_user = st.selectbox("Select User", list(users.keys()))
                
                if st.button("🌟 Make Premium"):
                    if isinstance(users[selected_user], str):
                        # Convert old format to new format
                        users[selected_user] = {
                            "password": users[selected_user],
                            "usage_count": 0,
                            "paid_user": True
                        }
                    else:
                        # Update existing user
                        users[selected_user]["paid_user"] = True
                    
                    save_users(users)
                    st.success(f"✅ User {selected_user} is now a premium user")
                    st.rerun()
                
                if st.button("🔄 Reset Usage Count"):
                    if isinstance(users[selected_user], str):
                        # Convert old format to new format
                        users[selected_user] = {
                            "password": users[selected_user],
                            "usage_count": 0,
                            "paid_user": False
                        }
                    else:
                        # Update existing user
                        users[selected_user]["usage_count"] = 0
                    
                    save_users(users)
                    st.success(f"✅ Usage count for {selected_user} has been reset")
                    st.rerun()
            
            with col2:
                if st.button("❌ Delete User"):
                    del users[selected_user]
                    save_users(users)
                    st.success(f"✅ User {selected_user} has been deleted")
                    st.rerun()
                
                if st.button("🔄 Convert All Users to New Format"):
                    for username, user_data in list(users.items()):
                        if isinstance(user_data, str):
                            users[username] = {
                                "password": user_data,
                                "usage_count": 0,
                                "paid_user": False
                            }
                    
                    save_users(users)
                    st.success("✅ All users converted to new format")
                    st.rerun()
    
    except Exception as e:
        st.error(f"Error processing user data: {str(e)}")
    
    # Logout button
    if st.button("🚪 Logout"):
        st.session_state.admin_authenticated = False
        st.rerun()

if __name__ == "__main__":
    admin_panel() 