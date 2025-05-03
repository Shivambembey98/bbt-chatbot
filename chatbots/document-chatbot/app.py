# import streamlit as st
# import boto3
# import os
# import random
# from extract_text import extract_text
# from bedrockapi import query_bedrock
# import base64
# import time
# import jwt  # for decoding JWT
# import psycopg2  # for database

# # AWS S3 Configuration
# S3_BUCKET = "chatbotbucket-12345"
# s3_client = boto3.client("s3")

# # PostgreSQL Configuration
# DB_CONFIG = {
#     "host": "your-db-host",
#     "port": 5432,
#     "database": "your-db-name",
#     "user": "your-db-user",
#     "password": "your-db-password"
# }

# def get_db_connection():
#     conn = psycopg2.connect(**DB_CONFIG)
#     return conn

# os.environ["STREAMLIT_WATCH_FILE"] = "false"

# st.set_page_config(page_title="Document Chatbot")

# # Accept JWT token from URL
# query_params = st.query_params
# jwt_token = query_params.get("token")

# # Setup JWT decoding
# JWT_SECRET = "your_jwt_secret_key"  # 🔴 Replace with your backend's secret
# JWT_ALGORITHM = "HS256"  # or whatever your backend uses

# # Decode JWT token
# if jwt_token:
#     try:
#         decoded_token = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#         user_name = decoded_token.get("username", "Guest User")  # fallback if username not found
#     except jwt.ExpiredSignatureError:
#         st.error("Session expired. Please login again.")
#         st.stop()
#     except jwt.InvalidTokenError:
#         st.error("Invalid session token. Please login again.")
#         st.stop()
# else:
#     st.error("No authentication token found. Please login again.")
#     st.stop()


# logo_path = "static/watermark.png"

# # Convert image to Base64
# with open(logo_path, "rb") as image_file:
#     encoded_logo = base64.b64encode(image_file.read()).decode()

# # Inject CSS to set the background image
# st.markdown(
#     f'''
#     <style>
#         .stApp {{
#             background: url("data:image/png;base64,{encoded_logo}") no-repeat center center fixed;
#             background-size: cover;
#             opacity: 1; /* Adjust transparency here, closer to 1 is more opaque */
#         }}
#         .p {{
#             position: absolute;
#             top: 60;
#             left: 0;
#             width: 100%;
#             background-color: rgba(255, 255, 255, 0.8); /* Optional background for readability */
#             text-align: center;
#             padding: 10px 0;
#             z-index: 1000;
#         }}
#     </style>
#     <div class="header">
#         <p style='font-size:50px;color:#000000;margin:0;'>🤖-What can I help you with?</p>
#     </div>
#     ''',
#     unsafe_allow_html=True,
# )

# # Custom CSS for chat styling
# st.markdown(
#     """
#     <style>
#         body { 
#             background-color: #337EFF;
#             color: white; 
#             background-size: cover;
#         }
#         .chat-container { 
#             max-width: 600px;
#             margin: auto; 
#         }
#         .chat-bubble { 
#             padding: 10px; 
#             border-radius: 10px; 
#             margin-bottom: 10px; 
#             display: inline-block; 
#             max-width: 70%; 
#             color: white; 
#         }
#         .user { 
#             background-color: #337EFF; 
#             text-align: left; 
#             float: right; 
#             clear: both; 
#             margin-right: 10px; 
#         }
#         .ai { 
#             background-color: #337EFF; 
#             text-align: left; 
#             float: left; 
#             clear: both; 
#             margin-left: 10px; 
#         }
#         @media (max-width: 900px) { 
#             .chat-container { margin: 0 10px; } 
#         }
#         div.stButton > button {
#             background-color: #337EFF !important; 
#             color: white !important;
#             border-radius: 10px !important; 
#             padding: 7px 20px !important;
#             font-size: 16px !important; 
#             border: none !important; 
#             margin-top: 27px;
#         }
#         div.stButton > button:hover { 
#             background-color: #004ED4 !important; 
#         }
#         div.stForm button {
#             background-color: #337EFF !important;
#             color: white !important;
#             border-radius: 70px !important;
#             padding: 17px 25px !important;
#             font-size: 16px !important;
#             font-weight: bold !important;
#             font-style: italic !important;
#             border: none !important;
#             position: fixed !important;
#             bottom: 15px;
#             justify-content: center;
#             z-index: 1000;
#             cursor: pointer;
#         }
#         div.stForm button:hover { 
#             background-color: #004ED4 !important; 
#         }
#         .stTextInput {
#             height:px;
#             padding: 10px 20px !important; 
#             width: 550px !important;
#             position: fixed !important; 
#             bottom: 15px; 
#             border-radius: 50px !important;
#             font-size: 16px !important;
#             background-color: #337EFF; 
#             z-index: 1000;
#         }
#         div.stForm {
#             border: none;
#             box-shadow: none;
#             padding: 0;
#         }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# # Initialize session state
# if "chat_history" not in st.session_state:
#     st.session_state.chat_history = []
# if "documents" not in st.session_state:
#     st.session_state.documents = []  # Store tuples (file_name, document_text)
# if "file_uploaded" not in st.session_state:
#     st.session_state.file_uploaded = False
# if "upload_message_shown" not in st.session_state:
#     st.session_state.upload_message_shown = False
# if "user_query" not in st.session_state:
#     st.session_state.user_query = ""
# if "user_name" not in st.session_state:
#     st.session_state.user_name = user_name  # Default name (you can make it dynamic later)
# if "signed_out" not in st.session_state:
#     st.session_state.signed_out = True

# # # If signed out, redirect immediately
# if st.session_state.get("signed_out", False):
#     st.markdown("""
#         <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/our-solutions" />
#         """, unsafe_allow_html=True)
#     st.stop()

# st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# # Sidebar - Multi-file uploader and clear chat option
# with st.sidebar:
#     st.markdown(
#         f"""
#         <div style='
#             background-color: rgba(51,126,255,0.1);
#             padding: 15px;
#             border-radius: 10px;
#             margin-bottom: 20px;
#             text-align: center;
#         '>
#             <h4 style='margin: 0; color: #004ED4;'> Hi, {st.session_state.user_name}!</h4>
#             {"<span style='color: white; background-color: #FFD700; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
#         </div>
#         """,
#         unsafe_allow_html=True,
#     )
#     st.write("Upload multiple documents to chat with them:")
#     uploaded_files = st.file_uploader(
#         "Upload PDFs", type=["pdf"], accept_multiple_files=True, key="multi_upload"
#     )

#     if st.button("🗑️ Clear Chat History", key="clear_chat"):
#         st.session_state.chat_history = []
#         st.session_state.file_uploaded = False
#         st.session_state.documents = []
#         st.session_state.upload_message_shown = False
#         st.rerun()
        
#     if st.button("🚪 Sign Out", key="sign_out"):
#         st.session_state.signed_out = True
#         st.rerun()
    
#      # Premium Purchase Button
#     st.markdown("---")
#     if st.button("💳 Subscribe"):
#         st.info("🚧 Premium purchase flow coming soon!")
#     st.markdown("### 🔓 Unlock Unlimited Questions")

# st.write("")
# st.write("")
# st.write("")
# st.write("")
# st.write("")

# # Display chat history
# if st.session_state.chat_history:
#     for speaker, text in st.session_state.chat_history:
#         alignment = "user" if speaker == "You" else "ai"
#         icon = "🧑‍💻" if speaker == "You" else "🤖 AI:"
#         st.markdown(f"<div class='chat-bubble {alignment}'><strong>{icon}</strong> {text}</div>", unsafe_allow_html=True)
# else:
#     st.write("")

# # Process multiple file uploads
# if uploaded_files:
#     for uploaded_file in uploaded_files:
#         file_name = uploaded_file.name
#         file_type = uploaded_file.type.split("/")[-1]

#         # Avoid re-uploading same file
#         if not any(doc[0] == file_name for doc in st.session_state.documents):
#             with st.spinner(f"Uploading {file_name}..."):
#                 s3_client.upload_fileobj(uploaded_file, S3_BUCKET, file_name)

#             with st.spinner(f"Extracting text from {file_name}..."):
#                 document_text = extract_text(file_name, file_type, s3_bucket=S3_BUCKET)

#             if not document_text.strip():
#                 st.error(f"{file_name} contains no text. Skipping...")
#             else:
#                 st.session_state.documents.append((file_name, document_text))
#                 st.session_state.file_uploaded = True

#     if not st.session_state.upload_message_shown and st.session_state.documents:
#         st.session_state.chat_history.append(("AI", f"{len(st.session_state.documents)} files uploaded successfully! Ask your question below."))
#         st.session_state.upload_message_shown = True
#         st.rerun()

# # Ensure unique form key on every render
# if "chat_count" not in st.session_state:
#     st.session_state["chat_count"] = 0
# if "user_query_input" not in st.session_state:
#     st.session_state["user_query_input"] = ""



# if "reset_input" in st.session_state and st.session_state.reset_input:
#     st.session_state.user_query_input = ""
#     st.session_state.reset_input = False

# # Chat Input Form
# with st.form(key=f"chat_form_{st.session_state.chat_count}"):
#     col1, col2 = st.columns([8, 2], gap="medium")
#     with col1:
#         text_input = st.text_input(
#             "",  # Empty label
#             key="user_query_input",
#             value=st.session_state.user_query_input,
#             placeholder="Ask something about the uploaded documents...",
#             label_visibility="collapsed"  # Hides the label
#         )
#     with col2:
#         send_button = st.form_submit_button("SEND")

# # Auto-submit if Enter is pressed
# if st.session_state.get("enter_pressed", False):
#     send_button = True
#     st.session_state.enter_pressed = False

# def display_animated_text(text, role="AI"):
#     placeholder = st.empty()
#     animated_text = ""
    
#     for char in text:
#         animated_text += char
#         placeholder.markdown(f"<div class='chat-bubble {role.lower()}'><strong>🤖 AI:</strong> {animated_text}</div>", unsafe_allow_html=True)
#         time.sleep(0.02)  # Adjust speed if needed

# MAX_TOKENS = 42000  # Bedrock input token limit

# # Limit to 10 free questions
# MAX_FREE_QUESTIONS = 6

# # Handle chat submission
# if send_button and text_input.strip():
#     if st.session_state["chat_count"] >= MAX_FREE_QUESTIONS:
#         # User hit limit — block interaction
#         premium_message = "🎉 You've used all free questions! To continue chatting, please upgrade to our Premium Membership."
#         st.session_state.chat_history.append(("AI", premium_message))
#         display_animated_text(premium_message, role="AI")
#         st.session_state.reset_input = True
#         st.rerun()
    
#     elif not st.session_state.file_uploaded or not st.session_state.documents:
#         # Show user's question immediately
#         st.session_state.chat_history.append(("You", text_input))
#         st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#         # AI response for missing documents
#         st.session_state.chat_history.append(("AI", "Hey, please upload one or more documents to start querying."))
#         display_animated_text("Hey, please upload one or more documents to start querying.", role="AI")

#         st.session_state.reset_input = True
#         st.rerun()
    
#     else:
#         # Select a random document
#         selected_doc = random.choice(st.session_state.documents)
#         document_text = selected_doc[1]

#         if len(document_text) > MAX_TOKENS:
#             warning_message = f"⚠️ The document **{selected_doc[0]}** is too large to process (limit: {MAX_TOKENS} characters). Try a smaller document or summarizing it."
#             st.session_state.chat_history.append(("AI", warning_message))
#             display_animated_text(warning_message, role="AI")  
#         else:
#             try:
#                 answer = query_bedrock(document_text, text_input)

#                 st.session_state.chat_history.append(("You", text_input))
#                 st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#                 st.session_state.chat_history.append(("AI", answer))
#                 display_animated_text(answer, role="AI")

#             except Exception as e:
#                 error_message = f"❌ An error occurred: {str(e)}"
#                 st.session_state.chat_history.append(("AI", error_message))
#                 display_animated_text(error_message, role="AI")

#         st.session_state.reset_input = True
#         st.session_state["chat_count"] += 1
#         st.rerun()














# import streamlit as st
# import boto3
# import os
# import random
# from extract_text import extract_text
# from bedrockapi import query_bedrock
# import base64
# import time
# import streamlit.components.v1 as components
# from streamlit_javascript import st_javascript

# # AWS S3 Configuration
# S3_BUCKET = "chatbotbucket-12345"
# s3_client = boto3.client("s3")

# os.environ["STREAMLIT_WATCH_FILE"] = "false"

# st.set_page_config(page_title="Document Chatbot")

# # ✅ Always reinitialize session state at the beginning
# required_session_keys = {
#     "user_name": "John Doe",
#     "premium_user": False,
#     "chat_history": [],
#     "documents": [],
#     "file_uploaded": False,
#     "upload_message_shown": False,
#     "user_query": "",
#     "chat_count": 0,
#     "user_query_input": "",
#     "reset_input": False,
# }

# for key, default_value in required_session_keys.items():
#     if key not in st.session_state:
#         st.session_state[key] = default_value

# logo_path = "static/watermark.png"

# # Convert image to Base64
# with open(logo_path, "rb") as image_file:
#     encoded_logo = base64.b64encode(image_file.read()).decode()

# # Inject CSS to set the background image
# st.markdown(
#     f'''
#     <style>
#         .stApp {{
#             background: url("data:image/png;base64,{encoded_logo}") no-repeat center center fixed;
#             background-size: cover;
#             opacity: 1; /* Adjust transparency here, closer to 1 is more opaque */
#         }}
#         .p {{
#             position: absolute;
#             top: 60;
#             left: 0;
#             width: 100%;
#             background-color: rgba(255, 255, 255, 0.8); /* Optional background for readability */
#             text-align: center;
#             padding: 10px 0;
#             z-index: 1000;
#         }}
#     </style>
#     <div class="header">
#         <p style='font-size:50px;color:#000000;margin:0;'>🤖-What can I help you with?</p>
#     </div>
#     ''',
#     unsafe_allow_html=True,
# )

# # Custom CSS for chat styling
# st.markdown(
#     """
#     <style>
#         body { 
#             background-color: #337EFF;
#             color: white; 
#             background-size: cover;
#         }
#         .chat-container { 
#             max-width: 600px;
#             margin: auto; 
#         }
#         .chat-bubble { 
#             padding: 10px; 
#             border-radius: 10px; 
#             margin-bottom: 10px; 
#             display: inline-block; 
#             max-width: 70%; 
#             color: white; 
#         }
#         .user { 
#             background-color: #337EFF; 
#             text-align: left; 
#             float: right; 
#             clear: both; 
#             margin-right: 10px; 
#         }
#         .ai { 
#             background-color: #337EFF; 
#             text-align: left; 
#             float: left; 
#             clear: both; 
#             margin-left: 10px; 
#         }
#         @media (max-width: 900px) { 
#             .chat-container { margin: 0 10px; } 
#         }
#         div.stButton > button {
#             background-color: #337EFF !important; 
#             color: white !important;
#             border-radius: 10px !important; 
#             padding: 7px 20px !important;
#             font-size: 16px !important; 
#             border: none !important; 
#             margin-top: 27px;
#         }
#         div.stButton > button:hover { 
#             background-color: #004ED4 !important; 
#         }
#         div.stForm button {
#             background-color: #337EFF !important;
#             color: white !important;
#             border-radius: 70px !important;
#             padding: 17px 25px !important;
#             font-size: 16px !important;
#             font-weight: bold !important;
#             font-style: italic !important;
#             border: none !important;
#             position: fixed !important;
#             bottom: 15px;
#             justify-content: center;
#             z-index: 1000;
#             cursor: pointer;
#         }
#         div.stForm button:hover { 
#             background-color: #004ED4 !important; 
#         }
#         .stTextInput {
#             height:px;
#             padding: 10px 20px !important; 
#             width: 550px !important;
#             position: fixed !important; 
#             bottom: 15px; 
#             border-radius: 50px !important;
#             font-size: 16px !important;
#             background-color: #337EFF; 
#             z-index: 1000;
#         }
#         div.stForm {
#             border: none;
#             box-shadow: none;
#             padding: 0;
#         }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# # If signed out, redirect immediately
# if st.session_state.get("signed_out", False):
#     st.markdown("""
#         <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/products/gen-ai" />
#         """, unsafe_allow_html=True)
#     st.stop()


# if "chat_history" not in st.session_state:
#     st.session_state.chat_history = []
# if "documents" not in st.session_state:
#     st.session_state.documents = []
# if "file_uploaded" not in st.session_state:
#     st.session_state.file_uploaded = False
# if "upload_message_shown" not in st.session_state:
#     st.session_state.upload_message_shown = False
# if "user_query" not in st.session_state:
#     st.session_state.user_query = ""
# if "chat_count" not in st.session_state:
#     st.session_state.chat_count = 0
# if "user_query_input" not in st.session_state:
#     st.session_state.user_query_input = ""
# if "premium_user" not in st.session_state:
#     st.session_state.premium_user = False  # 🚨 This is important 🚨
#     # Initialize important session variables early
# if "user_name" not in st.session_state:
#     st.session_state.user_name = "John Doe"  # Default name (you can make it dynamic later)
# if "signed_out" not in st.session_state:
#     st.session_state.signed_out = False


# st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# # Sidebar - Multi-file uploader and clear chat option
# with st.sidebar:
#     st.markdown(
#         f"""
#         <div style='
#             background-color: rgba(51,126,255,0.1);
#             padding: 15px;
#             border-radius: 10px;
#             margin-bottom: 20px;
#             text-align: center;
#         '>
#             <h4 style='margin: 0; color: #004ED4;'> Hi, {st.session_state.user_name}!</h4>
#             {"<span style='color: white; background-color: #FFD700; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
#         </div>
#         """,
#         unsafe_allow_html=True,
#     )

#     # --- File Upload & Buttons ---
#     st.write("Upload multiple documents to chat with them:")
#     uploaded_files = st.file_uploader(
#         "Upload PDFs or DOCX files", type=["pdf", "docx"], accept_multiple_files=True, key="multi_upload"
#     )

#     if st.button("🗑️ Clear Chat History", key="clear_chat"):
#         st.session_state.chat_history = []
#         st.session_state.file_uploaded = False
#         st.session_state.documents = []
#         st.session_state.upload_message_shown = False
#         st.rerun()

#     if st.button("🚪 Sign Out", key="sign_out"):
#         st.session_state.signed_out = True
#         st.rerun()

#     st.markdown("---")
    
#     if st.button("💳 Subscribe"):
#         RAZORPAY_KEY_ID = "rzp_live_v6qAzViosoOdnK"
#         RAZORPAY_AMOUNT = 100  # in paise

#         payment_html = f"""
#         <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
#         <script>
#         function openRazorpay() {{
#             var options = {{
#                 "key": "{RAZORPAY_KEY_ID}",
#                 "amount": "{RAZORPAY_AMOUNT}",
#                 "currency": "INR",
#                 "name": "Streamlit Premium",
#                 "description": "Access to premium features",
#                 "handler": function (response) {{
#                     localStorage.setItem("payment_success", "true");
#                     alert("✅ Payment successful! Reloading features...");
#                 }},
#                 "prefill": {{
#                     "name": "John Doe",
#                     "email": "johndoe@example.com"
#                 }},
#                 "theme": {{
#                     "color": "#337EFF"
#                 }}
#             }};
#             var rzp1 = new Razorpay(options);
#             rzp1.open();
#         }}
#         </script>

#         <button onclick="openRazorpay()" style="
#             background-color: #337EFF;
#             color: white;
#             padding: 10px 20px;
#             font-size: 18px;
#             border-radius: 10px;
#             border: none;
#             cursor: pointer;
#         ">Pay Now 💳</button>
#         """

#         components.html(payment_html, height=700)
#     payment_check = st_javascript("""await localStorage.getItem("payment_success");""")

#     if payment_check == "true":
#         st.session_state.premium_user = True
#         st.success("✅ Premium unlocked! Enjoy unlimited questions.")
#         st_javascript("""await localStorage.removeItem("payment_success");""")
#         time.sleep(1)  # optional small delay
#         st.rerun()     # force auto-refresh the app

# st.write("")
# st.write("")
# st.write("")
# st.write("")
# st.write("")

# # Initialize session state
# # if "chat_history" not in st.session_state:
# #     st.session_state.chat_history = []
# # if "documents" not in st.session_state:
# #     st.session_state.documents = []  # Store tuples (file_name, document_text)
# # if "file_uploaded" not in st.session_state:
# #     st.session_state.file_uploaded = False
# # if "upload_message_shown" not in st.session_state:
# #     st.session_state.upload_message_shown = False
# # if "user_query" not in st.session_state:
# #     st.session_state.user_query = ""


# # Display chat history
# if st.session_state.chat_history:
#     for speaker, text in st.session_state.chat_history:
#         alignment = "user" if speaker == "You" else "ai"
#         icon = "🧑‍💻" if speaker == "You" else "🤖 AI:"
#         st.markdown(f"<div class='chat-bubble {alignment}'><strong>{icon}</strong> {text}</div>", unsafe_allow_html=True)
# else:
#     st.write("")

# # Process multiple file uploads
# if uploaded_files:
#     for uploaded_file in uploaded_files:
#         file_name = uploaded_file.name
#         file_type = uploaded_file.type.split("/")[-1]

#         # Avoid re-uploading same file
#         if not any(doc[0] == file_name for doc in st.session_state.documents):
#             with st.spinner(f"Uploading {file_name}..."):
#                 s3_client.upload_fileobj(uploaded_file, S3_BUCKET, file_name)

#             with st.spinner(f"Extracting text from {file_name}..."):
#                 document_text = extract_text(file_name, file_type, s3_bucket=S3_BUCKET)

#             if not document_text.strip():
#                 st.error(f"{file_name} contains no text. Skipping...")
#             else:
#                 st.session_state.documents.append((file_name, document_text))
#                 st.session_state.file_uploaded = True

#     if not st.session_state.upload_message_shown and st.session_state.documents:
#         st.session_state.chat_history.append(("AI", f"{len(st.session_state.documents)} files uploaded successfully! Ask your question below."))
#         st.session_state.upload_message_shown = True
#         st.rerun()

# # Ensure unique form key on every render
# if "chat_count" not in st.session_state:
#     st.session_state["chat_count"] = 0
# if "user_query_input" not in st.session_state:
#     st.session_state["user_query_input"] = ""



# if "reset_input" in st.session_state and st.session_state.reset_input:
#     st.session_state.user_query_input = ""
#     st.session_state.reset_input = False

# # Chat Input Form
# with st.form(key=f"chat_form_{st.session_state.chat_count}"):
#     col1, col2 = st.columns([8, 2], gap="medium")
#     with col1:
#         text_input = st.text_input(
#             "",  # Empty label
#             key="user_query_input",
#             value=st.session_state.user_query_input,
#             placeholder="Ask something about the uploaded documents...",
#             label_visibility="collapsed"  # Hides the label
#         )
#     with col2:
#         send_button = st.form_submit_button("SEND")

# # Auto-submit if Enter is pressed
# if st.session_state.get("enter_pressed", False):
#     send_button = True
#     st.session_state.enter_pressed = False

# def display_animated_text(text, role="AI"):
#     placeholder = st.empty()
#     animated_text = ""
    
#     for char in text:
#         animated_text += char
#         placeholder.markdown(f"<div class='chat-bubble {role.lower()}'><strong>🤖 AI:</strong> {animated_text}</div>", unsafe_allow_html=True)
#         time.sleep(0.02)  

# MAX_TOKENS = 42000  


# MAX_FREE_QUESTIONS = 6

# if send_button and text_input.strip():
#     is_premium = st.session_state.get("premium_user", False)
#     if not st.session_state.get("premium_user", False) and st.session_state["chat_count"] >= MAX_FREE_QUESTIONS:
#         premium_message = "🎉 You've used all free questions! To continue chatting, please upgrade to our Premium Membership."
#         st.session_state.chat_history.append(("AI", premium_message))
#         display_animated_text(premium_message, role="AI")
#         st.session_state.reset_input = True
#         st.rerun()
        
#     elif not st.session_state.file_uploaded or not st.session_state.documents:
#         # Show user's question immediately
#         st.session_state.chat_history.append(("You", text_input))
#         st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#         # AI response for missing documents
#         st.session_state.chat_history.append(("AI", "Hey, please upload one or more documents to start querying."))
#         display_animated_text("Hey, please upload one or more documents to start querying.", role="AI")

#         st.session_state.reset_input = True
#         st.rerun()
    
#     else:
#         # Select a random document
#         selected_doc = random.choice(st.session_state.documents)
#         document_text = selected_doc[1]

#         if len(document_text) > MAX_TOKENS:
#             warning_message = f"⚠️ The document **{selected_doc[0]}** is too large to process (limit: {MAX_TOKENS} characters). Try a smaller document or summarizing it."
#             st.session_state.chat_history.append(("AI", warning_message))
#             display_animated_text(warning_message, role="AI")  
#         else:
#             try:
#                 answer = query_bedrock(document_text, text_input)

#                 st.session_state.chat_history.append(("You", text_input))
#                 st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#                 st.session_state.chat_history.append(("AI", answer))
#                 display_animated_text(answer, role="AI")

#             except Exception as e:
#                 error_message = f"❌ An error occurred: {str(e)}"
#                 st.session_state.chat_history.append(("AI", error_message))
#                 display_animated_text(error_message, role="AI")

#         st.session_state.reset_input = True
#         st.session_state["chat_count"] += 1
#         st.rerun()



























# import streamlit as st
# import boto3
# import os
# import random
# from extract_text import extract_text
# from bedrockapi import query_bedrock
# import base64
# import time
# import streamlit.components.v1 as components
# from streamlit_javascript import st_javascript


# query_params = st.query_params
# token = query_params.get("token", [])  # default to '1'

# if token:
#     st.set_page_config(page_title="Second Page")
#     st.title("Redirecting to Document Chatbot")
#     st_javascript(f"""localStorage.setItem("user_token", "{token}");""")
#     # JavaScript redirect using meta refresh
#     st.markdown("""
#         <meta http-equiv="refresh" content="1; url=/" />
#     """, unsafe_allow_html=True)
#     print("get token",token)
#     st.stop()  # Prevent rest of the script from running

# else:
#     # AWS S3 Configuration
#     S3_BUCKET = "chatbotbucket-12345"
#     s3_client = boto3.client("s3")

#     os.environ["STREAMLIT_WATCH_FILE"] = "false"

#     st.set_page_config(page_title="Document Chatbot")
#     # st_javascript(f"""localStorage.setItem("user_token", "{token}");""")

#     # ✅ Always reinitialize session state at the beginning
#     required_session_keys = {
#         "user_name": "John Doe",
#         "premium_user": False,
#         "chat_history": [],
#         "documents": [],
#         "file_uploaded": False,
#         "upload_message_shown": False,
#         "user_query": "",
#         "chat_count": 0,
#         "user_query_input": "",
#         "reset_input": False,
#     }

#     for key, default_value in required_session_keys.items():
#         if key not in st.session_state:
#             st.session_state[key] = default_value

#     logo_path = "static/watermark.png"

#     # Convert image to Base64
#     with open(logo_path, "rb") as image_file:
#         encoded_logo = base64.b64encode(image_file.read()).decode()

#     # Inject CSS to set the background image
#     st.markdown(
#         f'''
#         <style>
#             .stApp {{
#                 background: url("data:image/png;base64,{encoded_logo}") no-repeat center center fixed;
#                 background-size: cover;
#                 opacity: 1; /* Adjust transparency here, closer to 1 is more opaque */
#             }}
#             .p {{
#                 position: absolute;
#                 top: 60;
#                 left: 0;
#                 width: 100%;
#                 background-color: rgba(255, 255, 255, 0.8); /* Optional background for readability */
#                 text-align: center;
#                 padding: 10px 0;
#                 z-index: 1000;
#             }}
#         </style>
#         <div class="header">
#             <p style='font-size:50px;color:#000000;margin:0;'>🤖-What can I help you with?</p>
#         </div>
#         ''',
#         unsafe_allow_html=True,
#     )

#     # Custom CSS for chat styling
#     st.markdown(
#         """
#         <style>
#             body { 
#                 background-color: #337EFF;
#                 color: white; 
#                 background-size: cover;
#             }
#             .chat-container { 
#                 max-width: 600px;
#                 margin: auto; 
#             }
#             .chat-bubble { 
#                 padding: 10px; 
#                 border-radius: 10px; 
#                 margin-bottom: 10px; 
#                 display: inline-block; 
#                 max-width: 70%; 
#                 color: white; 
#             }
#             .user { 
#                 background-color: #337EFF; 
#                 text-align: left; 
#                 float: right; 
#                 clear: both; 
#                 margin-right: 10px; 
#             }
#             .ai { 
#                 background-color: #337EFF; 
#                 text-align: left; 
#                 float: left; 
#                 clear: both; 
#                 margin-left: 10px; 
#             }
#             @media (max-width: 900px) { 
#                 .chat-container { margin: 0 10px; } 
#             }
#             div.stButton > button {
#                 background-color: #337EFF !important; 
#                 color: white !important;
#                 border-radius: 10px !important; 
#                 padding: 7px 20px !important;
#                 font-size: 16px !important; 
#                 border: none !important; 
#                 margin-top: 27px;
#             }
#             div.stButton > button:hover { 
#                 background-color: #004ED4 !important; 
#             }
#             div.stForm button {
#                 background-color: #337EFF !important;
#                 color: white !important;
#                 border-radius: 70px !important;
#                 padding: 17px 25px !important;
#                 font-size: 16px !important;
#                 font-weight: bold !important;
#                 font-style: italic !important;
#                 border: none !important;
#                 position: fixed !important;
#                 bottom: 15px;
#                 justify-content: center;
#                 z-index: 1000;
#                 cursor: pointer;
#             }
#             div.stForm button:hover { 
#                 background-color: #004ED4 !important; 
#             }
#             .stTextInput {
#                 height:px;
#                 padding: 10px 20px !important; 
#                 width: 550px !important;
#                 position: fixed !important; 
#                 bottom: 15px; 
#                 border-radius: 50px !important;
#                 font-size: 16px !important;
#                 background-color: #337EFF; 
#                 z-index: 1000;
#             }
#             div.stForm {
#                 border: none;
#                 box-shadow: none;
#                 padding: 0;
#             }
#         </style>
#         """,
#         unsafe_allow_html=True,
#     )

#     # If signed out, redirect immediately
#     if st.session_state.get("signed_out", False):
#         st.markdown("""
#             <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/products/gen-ai" />
#             """, unsafe_allow_html=True)
#         st.stop()


#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = []
#     if "documents" not in st.session_state:
#         st.session_state.documents = []
#     if "file_uploaded" not in st.session_state:
#         st.session_state.file_uploaded = False
#     if "upload_message_shown" not in st.session_state:
#         st.session_state.upload_message_shown = False
#     if "user_query" not in st.session_state:
#         st.session_state.user_query = ""
#     if "chat_count" not in st.session_state:
#         st.session_state.chat_count = 0
#     if "user_query_input" not in st.session_state:
#         st.session_state.user_query_input = ""
#     if "premium_user" not in st.session_state:
#         st.session_state.premium_user = False  # 🚨 This is important 🚨
#         # Initialize important session variables early
#     if "user_name" not in st.session_state:
#         st.session_state.user_name = "John Doe"  # Default name (you can make it dynamic later)
#     if "signed_out" not in st.session_state:
#         st.session_state.signed_out = False


#     st.markdown('<div class="chat-container">', unsafe_allow_html=True)

#     # Sidebar - Multi-file uploader and clear chat option
#     with st.sidebar:
#         st.markdown(
#             f"""
#             <div style='
#                 background-color: rgba(51,126,255,0.1);
#                 padding: 15px;
#                 border-radius: 10px;
#                 margin-bottom: 20px;
#                 text-align: center;
#             '>
#                 <h4 style='margin: 0; color: #004ED4;'> Hi, {st.session_state.user_name}!</h4>
#                 {"<span style='color: white; background-color: #FFD700; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
#             </div>
#             """,
#             unsafe_allow_html=True,
#         )

#         # --- File Upload & Buttons ---
#         st.write("Upload multiple documents to chat with them:")
#         uploaded_files = st.file_uploader(
#             "Upload PDFs or DOCX files", type=["pdf", "docx"], accept_multiple_files=True, key="multi_upload"
#         )

#         if st.button("🗑️ Clear Chat History", key="clear_chat"):
#             st.session_state.chat_history = []
#             st.session_state.file_uploaded = False
#             st.session_state.documents = []
#             st.session_state.upload_message_shown = False
#             st.rerun()

#         if st.button("🚪 Sign Out", key="sign_out"):
#             st.session_state.signed_out = True
#             st.rerun()

#         st.markdown("---")
        
#         if st.button("💳 Subscribe"):
#             RAZORPAY_KEY_ID = "rzp_live_v6qAzViosoOdnK"
#             RAZORPAY_AMOUNT = 100  # in paise

#             payment_html = f"""
#             <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
#             <script>
#             function openRazorpay() {{
#                 var options = {{
#                     "key": "{RAZORPAY_KEY_ID}",
#                     "amount": "{RAZORPAY_AMOUNT}",
#                     "currency": "INR",
#                     "name": "Streamlit Premium",
#                     "description": "Access to premium features",
#                     "handler": function (response) {{
#                         window.location.href = "?payment=success";
#                     }},
#                     "prefill": {{
#                         "name": "John Doe",
#                         "email": "johndoe@example.com"
#                     }},
#                     "theme": {{
#                         "color": "#337EFF"
#                     }}
#                 }};
#                 var rzp1 = new Razorpay(options);
#                 rzp1.open();
#             }}
#             </script>

#             <button onclick="openRazorpay()" style="
#                 background-color: #337EFF;
#                 color: white;
#                 padding: 10px 20px;
#                 font-size: 18px;
#                 border-radius: 10px;
#                 border: none;
#                 cursor: pointer;
#             ">Pay Now 💳</button>
#             """

#             components.html(payment_html, height=700)
#         payment_check = st_javascript("""await localStorage.getItem("payment_success");""")

#         if payment_check == "true":
#             st.session_state.premium_user = True
#             st.success("✅ Premium unlocked! Enjoy unlimited questions.")
#             st_javascript("""await localStorage.removeItem("payment_success");""")
#             time.sleep(1)  # optional small delay
#             st.rerun()     # force auto-refresh the app

#     st.write("")
#     st.write("")
#     st.write("")
#     st.write("")
#     st.write("")

#     # Display chat history
#     if st.session_state.chat_history:
#         for speaker, text in st.session_state.chat_history:
#             alignment = "user" if speaker == "You" else "ai"
#             icon = "🧑‍💻" if speaker == "You" else "🤖 AI:"
#             st.markdown(f"<div class='chat-bubble {alignment}'><strong>{icon}</strong> {text}</div>", unsafe_allow_html=True)
#     else:
#         st.write("")

#     # Process multiple file uploads
#     if uploaded_files:
#         for uploaded_file in uploaded_files:
#             file_name = uploaded_file.name
#             file_type = uploaded_file.type.split("/")[-1]

#             # Avoid re-uploading same file
#             if not any(doc[0] == file_name for doc in st.session_state.documents):
#                 with st.spinner(f"Uploading {file_name}..."):
#                     s3_client.upload_fileobj(uploaded_file, S3_BUCKET, file_name)

#                 with st.spinner(f"Extracting text from {file_name}..."):
#                     document_text = extract_text(file_name, file_type, s3_bucket=S3_BUCKET)

#                 if not document_text.strip():
#                     st.error(f"{file_name} contains no text. Skipping...")
#                 else:
#                     st.session_state.documents.append((file_name, document_text))
#                     st.session_state.file_uploaded = True

#         if not st.session_state.upload_message_shown and st.session_state.documents:
#             st.session_state.chat_history.append(("AI", f"{len(st.session_state.documents)} files uploaded successfully! Ask your question below."))
#             st.session_state.upload_message_shown = True
#             st.rerun()

#     # Ensure unique form key on every render
#     if "chat_count" not in st.session_state:
#         st.session_state["chat_count"] = 0
#     if "user_query_input" not in st.session_state:
#         st.session_state["user_query_input"] = ""



#     if "reset_input" in st.session_state and st.session_state.reset_input:
#         st.session_state.user_query_input = ""
#         st.session_state.reset_input = False

#     # Chat Input Form
#     with st.form(key=f"chat_form_{st.session_state.chat_count}"):
#         col1, col2 = st.columns([8, 2], gap="medium")
#         with col1:
#             text_input = st.text_input(
#                 "",  # Empty label
#                 key="user_query_input",
#                 value=st.session_state.user_query_input,
#                 placeholder="Ask something about the uploaded documents...",
#                 label_visibility="collapsed"  # Hides the label
#             )
#         with col2:
#             send_button = st.form_submit_button("SEND")

#     # Auto-submit if Enter is pressed
#     if st.session_state.get("enter_pressed", False):
#         send_button = True
#         st.session_state.enter_pressed = False

#     def display_animated_text(text, role="AI"):
#         placeholder = st.empty()
#         animated_text = ""
        
#         for char in text:
#             animated_text += char
#             placeholder.markdown(f"<div class='chat-bubble {role.lower()}'><strong>🤖 AI:</strong> {animated_text}</div>", unsafe_allow_html=True)
#             time.sleep(0.02)  

#     MAX_TOKENS = 42000  


#     MAX_FREE_QUESTIONS = 6

#     if send_button and text_input.strip():
#         is_premium = st.session_state.get("premium_user", False)
#         if not st.session_state.get("premium_user", False) and st.session_state["chat_count"] >= MAX_FREE_QUESTIONS:
#             premium_message = "🎉 You've used all free questions! To continue chatting, please upgrade to our Premium Membership."
#             st.session_state.chat_history.append(("AI", premium_message))
#             display_animated_text(premium_message, role="AI")
#             st.session_state.reset_input = True
#             st.rerun()
            
#         elif not st.session_state.file_uploaded or not st.session_state.documents:
#             # Show user's question immediately
#             st.session_state.chat_history.append(("You", text_input))
#             st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#             # AI response for missing documents
#             st.session_state.chat_history.append(("AI", "Hey, please upload one or more documents to start querying."))
#             display_animated_text("Hey, please upload one or more documents to start querying.", role="AI")

#             st.session_state.reset_input = True
#             st.rerun()
        
#         else:
#             # Select a random document
#             selected_doc = random.choice(st.session_state.documents)
#             document_text = selected_doc[1]

#             if len(document_text) > MAX_TOKENS:
#                 warning_message = f"⚠️ The document **{selected_doc[0]}** is too large to process (limit: {MAX_TOKENS} characters). Try a smaller document or summarizing it."
#                 st.session_state.chat_history.append(("AI", warning_message))
#                 display_animated_text(warning_message, role="AI")  
#             else:
#                 try:
#                     answer = query_bedrock(document_text, text_input)

#                     st.session_state.chat_history.append(("You", text_input))
#                     st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

#                     st.session_state.chat_history.append(("AI", answer))
#                     display_animated_text(answer, role="AI")

#                 except Exception as e:
#                     error_message = f"❌ An error occurred: {str(e)}"
#                     st.session_state.chat_history.append(("AI", error_message))
#                     display_animated_text(error_message, role="AI")

#             st.session_state.reset_input = True
#             st.session_state["chat_count"] += 1
#             st.rerun()










import streamlit as st
import boto3
import os
import random
from extract_text import extract_text
from bedrockapi import query_bedrock
import base64
import time
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript


query_params = st.query_params
token = query_params.get("token", []) 

if token:
    st.set_page_config(page_title="Second Page")
    st.title("Redirecting to Document Chatbot")
    st_javascript(f"""localStorage.setItem("user_token", "{token}");""")
    st.markdown("""
        <meta http-equiv="refresh" content="1; url=/document-chatbot/" />
    """, unsafe_allow_html=True)
    print("get token",token)
    st.stop() 

else:
    # AWS S3 Configuration
    S3_BUCKET = "chatbotbucket-12345"
    s3_client = boto3.client("s3")

    os.environ["STREAMLIT_WATCH_FILE"] = "false"

    st.set_page_config(page_title="Document Chatbot")

    # ✅ Always reinitialize session state at the beginning
    required_session_keys = {
        "user_name": "John Doe",
        "premium_user": False,
        "chat_history": [],
        "documents": [],
        "file_uploaded": False,
        "upload_message_shown": False,
        "user_query": "",
        "chat_count": 0,
        "user_query_input": "",
        "reset_input": False,
    }

    for key, default_value in required_session_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    logo_path = "static/watermark.png"

    # Convert image to Base64
    with open(logo_path, "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()

    # Inject CSS to set the background image
    st.markdown(
        f'''
        <style>
            .stApp {{
                background: url("data:image/png;base64,{encoded_logo}") no-repeat center center fixed;
                background-size: cover;
                opacity: 1; /* Adjust transparency here, closer to 1 is more opaque */
            }}
            .p {{
                position: absolute;
                top: 60;
                left: 0;
                width: 100%;
                background-color: rgba(255, 255, 255, 0.8); /* Optional background for readability */
                text-align: center;
                padding: 10px 0;
                z-index: 1000;
            }}
        </style>
        <div class="header">
            <p style='font-size:50px;color:#000000;margin:0;'>🤖-What can I help you with?</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    # Custom CSS for chat styling
    st.markdown(
        """
        <style>
            body { 
                background-color: #337EFF;
                color: white; 
                background-size: cover;
            }
            .chat-container { 
                max-width: 600px;
                margin: auto; 
            }
            .chat-bubble { 
                padding: 10px; 
                border-radius: 10px; 
                margin-bottom: 10px; 
                display: inline-block; 
                max-width: 70%; 
                color: white; 
            }
            .user { 
                background-color: #337EFF; 
                text-align: left; 
                float: right; 
                clear: both; 
                margin-right: 10px; 
            }
            .ai { 
                background-color: #337EFF; 
                text-align: left; 
                float: left; 
                clear: both; 
                margin-left: 10px; 
            }
            @media (max-width: 900px) { 
                .chat-container { margin: 0 10px; } 
            }
            div.stButton > button {
                background-color: #337EFF !important; 
                color: white !important;
                border-radius: 10px !important; 
                padding: 7px 20px !important;
                font-size: 16px !important; 
                border: none !important; 
                margin-top: 27px;
            }
            div.stButton > button:hover { 
                background-color: #004ED4 !important; 
            }
            div.stForm button {
                background-color: #337EFF !important;
                color: white !important;
                border-radius: 70px !important;
                padding: 17px 25px !important;
                font-size: 16px !important;
                font-weight: bold !important;
                font-style: italic !important;
                border: none !important;
                position: fixed !important;
                bottom: 15px;
                justify-content: center;
                z-index: 1000;
                cursor: pointer;
            }
            div.stForm button:hover { 
                background-color: #004ED4 !important; 
            }
            .stTextInput {
                height:px;
                padding: 10px 20px !important; 
                width: 550px !important;
                position: fixed !important; 
                bottom: 15px; 
                border-radius: 50px !important;
                font-size: 16px !important;
                background-color: #337EFF; 
                z-index: 1000;
            }
            div.stForm {
                border: none;
                box-shadow: none;
                padding: 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # If signed out, redirect immediately
    if st.session_state.get("signed_out", False):
        st.markdown("""
            <meta http-equiv="refresh" content="0; url=https://www.bellblazetech.com/products/gen-ai" />
            """, unsafe_allow_html=True)
        st.stop()


    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "documents" not in st.session_state:
        st.session_state.documents = []
    if "file_uploaded" not in st.session_state:
        st.session_state.file_uploaded = False
    if "upload_message_shown" not in st.session_state:
        st.session_state.upload_message_shown = False
    if "user_query" not in st.session_state:
        st.session_state.user_query = ""
    if "chat_count" not in st.session_state:
        st.session_state.chat_count = 0
    if "user_query_input" not in st.session_state:
        st.session_state.user_query_input = ""
    if "premium_user" not in st.session_state:
        st.session_state.premium_user = False  # 🚨 This is important 🚨
        # Initialize important session variables early
    if "user_name" not in st.session_state:
        st.session_state.user_name = "John Doe"  # Default name (you can make it dynamic later)
    if "signed_out" not in st.session_state:
        st.session_state.signed_out = False


    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    # Sidebar - Multi-file uploader and clear chat option
    with st.sidebar:
        st.markdown(
            f"""
            <div style='
                background-color: rgba(51,126,255,0.1);
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
                text-align: center;
            '>
                <h4 style='margin: 0; color: #004ED4;'> Hi, {st.session_state.user_name}!</h4>
                {"<span style='color: white; background-color: #FFD700; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --- File Upload & Buttons ---
        st.write("Upload multiple documents to chat with them:")
        uploaded_files = st.file_uploader(
            "Upload PDFs or DOCX files", type=["pdf", "docx"], accept_multiple_files=True, key="multi_upload"
        )

        if st.button("🗑️ Clear Chat History", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.file_uploaded = False
            st.session_state.documents = []
            st.session_state.upload_message_shown = False
            st.rerun()

        if st.button("🚪 Sign Out", key="sign_out"):
            st.session_state.signed_out = True
            st.rerun()

        st.markdown("---")
        
        if st.button("💳 Subscribe"):
            RAZORPAY_KEY_ID = "rzp_live_v6qAzViosoOdnK"
            RAZORPAY_AMOUNT = 100  # in paise

            payment_html = f"""
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
            function openRazorpay() {{
                var options = {{
                    "key": "{RAZORPAY_KEY_ID}",
                    "amount": "{RAZORPAY_AMOUNT}",
                    "currency": "INR",
                    "name": "Streamlit Premium",
                    "description": "Access to premium features",
                    "handler": function (response) {{
                        window.location.href = "?payment=success";
                    }},
                    "prefill": {{
                        "name": "John Doe",
                        "email": "johndoe@example.com"
                    }},
                    "theme": {{
                        "color": "#337EFF"
                    }}
                }};
                var rzp1 = new Razorpay(options);
                rzp1.open();
            }}
            </script>

            <button onclick="openRazorpay()" style="
                background-color: #337EFF;
                color: white;
                padding: 10px 20px;
                font-size: 18px;
                border-radius: 10px;
                border: none;
                cursor: pointer;
            ">Pay Now 💳</button>
            """

            components.html(payment_html, height=700)
        payment_check = st_javascript("""await localStorage.getItem("payment_success");""")

        if payment_check == "true":
            st.session_state.premium_user = True
            st.success("✅ Premium unlocked! Enjoy unlimited questions.")
            st_javascript("""await localStorage.removeItem("payment_success");""")
            time.sleep(1)  # optional small delay
            st.rerun()     # force auto-refresh the app

    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.write("")

    # Display chat history
    if st.session_state.chat_history:
        for speaker, text in st.session_state.chat_history:
            alignment = "user" if speaker == "You" else "ai"
            icon = "🧑‍💻" if speaker == "You" else "🤖 AI:"
            st.markdown(f"<div class='chat-bubble {alignment}'><strong>{icon}</strong> {text}</div>", unsafe_allow_html=True)
    else:
        st.write("")

    # Process multiple file uploads
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            file_type = uploaded_file.type.split("/")[-1]

            # Avoid re-uploading same file
            if not any(doc[0] == file_name for doc in st.session_state.documents):
                with st.spinner(f"Uploading {file_name}..."):
                    s3_client.upload_fileobj(uploaded_file, S3_BUCKET, file_name)

                with st.spinner(f"Extracting text from {file_name}..."):
                    document_text = extract_text(file_name, file_type, s3_bucket=S3_BUCKET)

                if not document_text.strip():
                    st.error(f"{file_name} contains no text. Skipping...")
                else:
                    st.session_state.documents.append((file_name, document_text))
                    st.session_state.file_uploaded = True

        if not st.session_state.upload_message_shown and st.session_state.documents:
            st.session_state.chat_history.append(("AI", f"{len(st.session_state.documents)} files uploaded successfully! Ask your question below."))
            st.session_state.upload_message_shown = True
            st.rerun()

    # Ensure unique form key on every render
    if "chat_count" not in st.session_state:
        st.session_state["chat_count"] = 0
    if "user_query_input" not in st.session_state:
        st.session_state["user_query_input"] = ""



    if "reset_input" in st.session_state and st.session_state.reset_input:
        st.session_state.user_query_input = ""
        st.session_state.reset_input = False

    # Chat Input Form
    with st.form(key=f"chat_form_{st.session_state.chat_count}"):
        col1, col2 = st.columns([8, 2], gap="medium")
        with col1:
            text_input = st.text_input(
                "",  # Empty label
                key="user_query_input",
                value=st.session_state.user_query_input,
                placeholder="Ask something about the uploaded documents...",
                label_visibility="collapsed"  # Hides the label
            )
        with col2:
            send_button = st.form_submit_button("SEND")

    # Auto-submit if Enter is pressed
    if st.session_state.get("enter_pressed", False):
        send_button = True
        st.session_state.enter_pressed = False

    def display_animated_text(text, role="AI"):
        placeholder = st.empty()
        animated_text = ""
        
        for char in text:
            animated_text += char
            placeholder.markdown(f"<div class='chat-bubble {role.lower()}'><strong>🤖 AI:</strong> {animated_text}</div>", unsafe_allow_html=True)
            time.sleep(0.02)  

    MAX_TOKENS = 42000  


    MAX_FREE_QUESTIONS = 6

    if send_button and text_input.strip():
        is_premium = st.session_state.get("premium_user", False)
        if not st.session_state.get("premium_user", False) and st.session_state["chat_count"] >= MAX_FREE_QUESTIONS:
            premium_message = "🎉 You've used all free questions! To continue chatting, please upgrade to our Premium Membership."
            st.session_state.chat_history.append(("AI", premium_message))
            display_animated_text(premium_message, role="AI")
            st.session_state.reset_input = True
            st.rerun()
            
        elif not st.session_state.file_uploaded or not st.session_state.documents:
            # Show user's question immediately
            st.session_state.chat_history.append(("You", text_input))
            st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

            # AI response for missing documents
            st.session_state.chat_history.append(("AI", "Hey, please upload one or more documents to start querying."))
            display_animated_text("Hey, please upload one or more documents to start querying.", role="AI")

            st.session_state.reset_input = True
            st.rerun()
        
        else:
            # Select a random document
            selected_doc = random.choice(st.session_state.documents)
            document_text = selected_doc[1]

            if len(document_text) > MAX_TOKENS:
                warning_message = f"⚠️ The document **{selected_doc[0]}** is too large to process (limit: {MAX_TOKENS} characters). Try a smaller document or summarizing it."
                st.session_state.chat_history.append(("AI", warning_message))
                display_animated_text(warning_message, role="AI")  
            else:
                try:
                    answer = query_bedrock(document_text, text_input)

                    st.session_state.chat_history.append(("You", text_input))
                    st.markdown(f"<div class='chat-bubble user'><strong>🧑‍💻 You:</strong> {text_input}</div>", unsafe_allow_html=True)

                    st.session_state.chat_history.append(("AI", answer))
                    display_animated_text(answer, role="AI")

                except Exception as e:
                    error_message = f"❌ An error occurred: {str(e)}"
                    st.session_state.chat_history.append(("AI", error_message))
                    display_animated_text(error_message, role="AI")

            st.session_state.reset_input = True
            st.session_state["chat_count"] += 1
            st.rerun()
