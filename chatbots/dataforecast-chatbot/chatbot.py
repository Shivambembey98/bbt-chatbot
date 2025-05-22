import os
import json
import pandas as pd
import streamlit as st
import logging
import time
from auth import increment_usage, DATA_DIR
from db_storage import load_chat_history, save_chat_history, delete_chat_history

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reference to directory (kept for compatibility)
CHAT_HISTORY_DIR = os.path.join(DATA_DIR, "chat_history")

def load_user_chat_history(username):
    """Load chat history from database"""
    try:
        # Load from database
        chat_history = load_chat_history(username)
        logger.info(f"Chat history for {username} loaded from database successfully")
        return chat_history
    except Exception as e:
        logger.error(f"Error loading chat history from database: {str(e)}")
        return []

def save_user_chat_history(username, messages):
    """Save chat history to database"""
    try:
        # Save to PostgreSQL database
        success = save_chat_history(username, messages)
        if success:
            logger.info(f"Chat history for {username} saved to database successfully")
        else:
            logger.error("Database save operation failed")
    except Exception as e:
        logger.error(f"Error saving chat history to database: {str(e)}")

def clear_user_chat_history(username):
    """Clear chat history from database"""
    try:
        # Delete from database
        success = delete_chat_history(username)
        if success:
            logger.info(f"Chat history for {username} deleted from database successfully")
        else:
            logger.error(f"Failed to delete chat history for {username}")
    except Exception as e:
        logger.error(f"Error deleting chat history from database: {str(e)}")
    
    st.session_state.messages = []
    st.success("✅ Chat history cleared!")
    st.rerun()

# 📤 Process User Input and Get Response
def query_bedrock_stream(user_input, df, bedrock_client):
    # Get sample data as text
    df_sample = df.head(5).to_string()
    df_summary = df.describe().to_string()
    
    # Enhanced prompt focused on file uploads and data analysis with improved response quality
    prompt = f"""
    You are a professional data analyst assistant specialized in file uploads and data processing. You provide insightful, accurate, and business-focused responses about datasets.

    Dataset Information:
    - Filename: {getattr(df, '_filename', 'Uploaded dataset')}
    - Format: {getattr(df, '_format', 'CSV/Excel/Other')}
    - Number of Rows: {len(df)}
    - Number of Columns: {len(df.columns)}
    - Columns: {', '.join(df.columns)}
    
    Sample Data (first 5 rows):
    {df_sample}
    
    Statistical Summary:
    {df_summary}
    
    User's Question: {user_input}
    
    Provide a concise, professional response that:
    1. Directly answers the question with precision and clarity
    2. Offers data-driven insights relevant to the user's specific query
    3. Highlights important patterns or anomalies in the dataset when relevant
    4. Provides practical recommendations for data optimization or analysis
    5. Maintains a helpful, business-oriented tone throughout
    
    For file upload questions:
    - Be specific about supported formats (CSV, XLS, XLSX, JSON, PARQUET, PDF)
    - Mention the 5MB file size limit when relevant
    - Explain data validation processes
    - Suggest best practices for data preparation

    Structure your response with clear paragraphs, bullet points for lists, and emphasize key insights.
    """

    payload = {
        "modelId": "amazon.titan-text-lite-v1",
        "contentType": "application/json",
        "accept": "application/json",
        "body": {
            "inputText": prompt[:4000],
            "textGenerationConfig": {
                "maxTokenCount": 500,
                "stopSequences": [],
                "temperature": 0.7,
                "topP": 0.9
            }
        }
    }

    try:
        response = bedrock_client.invoke_model(
            body=json.dumps(payload["body"]),
            modelId=payload["modelId"],
            accept=payload["accept"],
            contentType=payload["contentType"]
        )

        result = json.loads(response["body"].read())
        full_response = result["results"][0]["outputText"]
        return full_response.strip()

    except Exception as e:
        return f"❌ Error: {str(e)}"

# 🧠 Chatbot Section
def chatbot_section(dataframes, file_names, bedrock_client):
    # Check if user is authenticated before proceeding
    if not st.session_state.get("authenticated", False):
        logger.info("User not authenticated - chatbot unavailable")
        st.warning("⚠️ Please log in to use the chat assistant.")
        return
        
    st.subheader("🤖 Chat with Your Dataset")

    # Use default username
    username = st.session_state.username

    # Initialize chat messages
    if "messages" not in st.session_state:
        # Load from history or initialize new
        st.session_state.messages = []
        history = load_user_chat_history(username)
        
        # Convert history to message format
        for item in history:
            st.session_state.messages.append({"role": "user", "content": item["question"]})
            st.session_state.messages.append({"role": "assistant", "content": item["answer"]})
        
        # Add welcome message if empty
        if not st.session_state.messages:
            st.session_state.messages.append({
                "role": "assistant", 
                "content": "Hello! I'm your professional data assistant. I can help you with file uploads, data analysis, and insights. How can I assist you today?"
            })
    
    # Place the Clear Conversation button in the sidebar
    if st.sidebar.button("🧹 Clear Conversation", key="clear_chat_button"):
        # Reset the usage tracking when chat is cleared
        st.session_state.chat_submission_counted = False
        clear_user_chat_history(username)

    # Display all chat messages first
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    user_input = st.chat_input("Ask me about your uploaded files or data analysis...")
    
    # Initialize usage tracking for chat
    if "chat_submission_counted" not in st.session_state:
        st.session_state.chat_submission_counted = False

    # Process when submitted
    if user_input:
        if not dataframes:
            st.error("Please upload at least one dataset first.")
            return
        
        # Count usage for this chat interaction if not already counted
        if not st.session_state.chat_submission_counted:
            increment_usage()
            st.session_state.chat_submission_counted = True
            
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Get selected dataset
        if len(dataframes) > 1:
            selected_df_index = st.selectbox("Select Dataset to Query", file_names, key="dataset_select")
            selected_df = dataframes[file_names.index(selected_df_index)]
        else:
            selected_df = dataframes[0]
            # Add filename attribute to dataframe
            selected_df._filename = file_names[0]
            selected_df._format = file_names[0].split('.')[-1].upper()
        
        # Generate assistant response with streaming effect
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            # For real streaming effect, build up the response gradually
            full_response = query_bedrock_stream(user_input, selected_df, bedrock_client)
            
            # Display response with a typing effect
            response_text = ""
            for i in range(min(len(full_response),1000)):  # Cap at 100 chars for the animation
                response_text += full_response[i]
                response_placeholder.markdown(response_text + "▌")
                time.sleep(0.01)  # Small delay for typing effect
            
            # Show the rest of the response instantly
            response_placeholder.markdown(full_response)
            
            # Save the conversation
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_user_chat_history(username, [
                {"question": msg["content"], "answer": st.session_state.messages[i+1]["content"]}
                for i, msg in enumerate(st.session_state.messages) 
                if msg["role"] == "user" and i+1 < len(st.session_state.messages)
            ])
