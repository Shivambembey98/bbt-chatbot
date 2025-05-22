import streamlit as st
import os
import random
from extract_text import extract_text
from bedrockapi import query_bedrock
import base64
import time
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
import boto3
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import errors
import urllib
from psycopg2.errors import UniqueViolation

load_dotenv()
st.set_page_config(page_title="Document Chatbot")
STATIC_DIR = "static"

SECRET_KEY = os.getenv("SECRET_KEY")

params         = st.query_params
token          = params.get("token",         "")
app_id         = params.get("app_id",         "document-chatbot")


if token:
    print("1")
    try:
        print("2")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        st.session_state["user_token"] = token
        st.session_state.user_name   = decoded.get("name",  "")
        st.session_state.user_email  = decoded.get("email", "")
        st.session_state.premium_user = False
        st.query_params.clear()
        st.rerun()

    except InvalidTokenError:
        st.error("Invalid token. Please log in again.")
        st.stop()
    except ExpiredSignatureError:
        st.error("Session expired. Please log in again.")
        st.stop()

if "payment" in st.query_params and st.query_params.get("payment") == "success" and "transaction_id" in st.query_params:
    print("Detected payment success in URL, processing payment first")

    payment_success = st.query_params.get("payment", "")
    txn_id = st.query_params.get("transaction_id", "")
    name = st.query_params.get("name", "")
    email = st.query_params.get("email", "")
    phone = st.query_params.get("phone", "")
    app_id = st.query_params.get("app_id", "dataforecast-chatbot")
    order_id = txn_id

    if "payment_processed" not in st.session_state or not st.session_state.payment_processed:
        print(f"Processing payment success at beginning: txn_id={txn_id}, name={name}, email={email}")

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

        st.session_state.user_name = name
        st.session_state.premium_user = True
        st.session_state.payment_processed = True
        st.session_state.authenticated = True

        st.balloons()
        st.success("✅ Payment successful! Premium features unlocked!")

        # Clean URL programmatically
        st.query_params.clear()

        # Try to save to database, but continue even if it fails
        conn = None
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                dbname=os.getenv("DB_NAME"),
                connect_timeout=5  # Add timeout to prevent hanging
            )
            cursor = conn.cursor()
            insert_query = """
                INSERT INTO bbt_tempusers(name, email, phone, app_id, order_id)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (name, email, phone, app_id, order_id))
            conn.commit()
            print("Payment record saved to database successfully")
        except Exception as e:
            print(f"❌ Error saving payment to database: {str(e)}")
            # Don't show error to user, just log it
            if conn:
                try:
                    conn.rollback()  # Rollback any failed transaction
                except Exception:
                    pass
        finally:
            # Always close the connection in the finally block
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        time.sleep(0.2)
        print("Payment processed successfully, rerunning with clean URL")
        st.rerun()

# if token:
#     print("in if token")
#     try:
#         print(token)
#         st_javascript(f"localStorage.setItem('user_token', '{token}');")
#         print("hello1")
#         decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
#         print("hello2")
#         print(decoded)
#         name = decoded.get("name", "Unknown User")
#         # st_javascript(f"sessionStorage.setItem('user_name', '{name}');")
#         st_javascript(f"localStorage.setItem('user_name', '{name}');")
#         email = decoded.get("email", "No Email")
#         print(email)
#         st_javascript(f"localStorage.setItem('user_email', '{email}');")
#         # Set session state
#         st.session_state.user_name = name
#         st.session_state.user_email = email
#         st.session_state.premium_user = True
 
#         # Redirect after 1 second
#         st.title("Authenticating...")
#         st.markdown("""<meta http-equiv='refresh' content='1; url=/' />""", unsafe_allow_html=True)
#         st.stop()
#     except InvalidTokenError:
#         print("invalid token")
#         st.error("Invalid token. Please login again.")
#     except ExpiredSignatureError:
#         print("If token session expired")
#         st.error("Session expired. Please login again.")
#         st.stop()
 
else:
    print("3")
    # AWS S3 Configuration
    S3_BUCKET = "chatbotbucket-12345"
    s3_client = boto3.client("s3")
   
    os.environ["STREAMLIT_WATCH_FILE"] = "false"
   
    name = "Unknown User"  

    if not st.session_state.get("user_name") and not st.session_state.get("payment_processed"):
        print("1234")
        print("Unauthorized")
        st.error("🔒 Unauthorized. Please log in on the original tab to continue. Link for Login :- http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/login?DomainPath=/document-chatbot")
        st.stop()
   
    required_session_keys = {
        "user_name": name,
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
 
    with open(logo_path, "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()
 
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
            <meta http-equiv="refresh" content="0; url=http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/our-solutions" />
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
        st.session_state.premium_user = False
    if "signed_out" not in st.session_state:
        st.session_state.signed_out = False
 
 
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
 
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
                {"<span style='color: black; background-color: #FFFFFF; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
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
            # clear the per-tab token
            st_javascript("sessionStorage.clear();")
            st.session_state.signed_out = True
            st.rerun()
 
        
        st.markdown("---")

        if st.button("💳 Subscribe"):
            token = st.session_state.get("user_token", "")
            if not token:
                st.warning("Log in first.")
            else:
                url = (
                "https://paymentdocumentchatbot.s3.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html?"
                + urllib.parse.urlencode({"app_id": app_id, "token": token})
                )
                # Inject JavaScript to redirect
                st.markdown(
                    f"""
                    <meta http-equiv="refresh" content="0; url={url}">
                    <script>
                        window.location.href = "{url}";
                    </script>
                    """,
                    unsafe_allow_html=True
                )
   
        # if st.button("💳 Subscribe"):
        #     js = """
        #         <script>
        #         const token = localStorage.getItem('user_token');
        #         if (!token) {
        #             alert("No token found—please log in again.");
        #         } else {
        #             const params = new URLSearchParams({
        #             app_id: "document-chatbot",
        #             token: token
        #             });
        #             window.open(
        #             "http://paymentdocumentchatbot.s3-website.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html?" + params.toString()
        #             );
        #         }
        #         </script>
        #     """
        #     components.html(js, height=0, scrolling=False)
       

    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.write("")
 
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
           # file_type = uploaded_file.type.split("/")[-1]
            _, ext = os.path.splitext(uploaded_file.name)
            file_type = ext.lstrip(".").lower()
 
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
 
 
    if st.session_state.get("premium_user", False):
        MAX_QUESTIONS = 20
    else:
        MAX_QUESTIONS = 3
 
    if send_button and text_input.strip():
        is_premium = st.session_state.get("premium_user", False)
        if st.session_state["chat_count"] >= MAX_QUESTIONS:
            limit_message = "🎯 You've reached your question limit."
            if st.session_state.get("premium_user", False):
                limit_message += " Thank you for subscribing! You've reached your 20-question premium quota."
            else:
                limit_message += " To continue, please upgrade to Premium."
 
            st.session_state.chat_history.append(("AI", limit_message))
            display_animated_text(limit_message, role="AI")
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













# import streamlit as st
# st.set_page_config(page_title="Document Chatbot")
# import os
# import random
# from extract_text import extract_text
# from bedrockapi import query_bedrock
# import base64
# import time
# import streamlit.components.v1 as components
# from streamlit_javascript import st_javascript
# import boto3
# import jwt
# from jwt import ExpiredSignatureError, InvalidTokenError
# from dotenv import load_dotenv
# import os
# import psycopg2
 
# load_dotenv()
 
# STATIC_DIR = "static"

# SECRET_KEY = os.getenv("SECRET_KEY")

# token_param = st.query_params.get("token", [""])
# txn_param   = st.query_params.get("transaction_id", [""])
# payment_success = st.query_params.get("payment", "")
# print(token_param)
# if payment_success == "success" and token_param and txn_param:
#     try:
#         # decode user from the same JWT you passed in
#         decoded = jwt.decode(token_param, SECRET_KEY, algorithms=["HS256"])
#         print(decoded)
#         st.session_state.user_name    = decoded.get("name")
#         st.session_state.user_email   = decoded.get("email")
#         st.session_state.premium_user = True

#         # stash both into localStorage for your Step 4 logic
#         st_javascript(f"localStorage.setItem('user_token','{token_param}');")
#         st_javascript(f"localStorage.setItem('transaction_id','{txn_param}');")

#         # prune the URL so it’s just "?payment=success"
#         st_javascript(
#           "window.history.replaceState(null,'', window.location.pathname + '?payment=success');"
#         )
#         # stop so the page reloads with only payment=success
#         st.stop()
#     except InvalidTokenError:
#         st.error("Invalid token. Please login again.")
#         st.stop()
#     except ExpiredSignatureError:
#         st.error("Session expired. Please login again.")
#         st.stop()

# query_params = st.query_params
# token = query_params.get("token", "")
# txn_id_js = st_javascript("await localStorage.getItem('transaction_id');", key="txn_id_js")
# name = st.query_params.get("name", "")
# email = st.query_params.get("email", "")
# phone = st.query_params.get("phone", "")
# app_id = st.query_params.get("app_id", "document-chatbot") 
 


# if "payment_processed" not in st.session_state:            
#     st.session_state.payment_processed = False

# payment_success = st.query_params.get("payment", [""])
# # grab the stored transaction_id
# txn_id_js = st_javascript("await localStorage.getItem('transaction_id');")

# if payment_success == "success" and not st.session_state.payment_processed:
#     txn_id = txn_id_js
#     if txn_id:
#         try:
#             conn = psycopg2.connect(
#                 host=os.getenv("DB_HOST"),
#                 user=os.getenv("DB_USER"),
#                 password=os.getenv("DB_PASSWORD"),
#                 dbname=os.getenv("DB_NAME")
#             )
#             cursor = conn.cursor()
#             cursor.execute(
#                 "INSERT INTO bbt_tempusers(name, email, phone, app_id, order_id) VALUES (%s,%s,%s,%s,%s)",
#                 (
#                   st.session_state.user_name,
#                   st.session_state.user_email,
#                   None,                    # phone is optional now
#                   "document-chatbot",      # or pull from session if dynamic
#                   txn_id
#                 )
#             )
#             conn.commit()
#             cursor.close()
#             conn.close()

#             # mark done & unlock
#             st.session_state.payment_processed = True
#             st.session_state.premium_user     = True
#             st.success("✅ Payment successful. Premium features unlocked!")

#             # clean up the URL again, just in case
#             st_javascript(
#               "window.history.replaceState(null,'', window.location.pathname + '?payment=success');"
#             )
#             st.rerun()

#         except psycopg2.Error as err:
#             st.error(f"❌ Database error: {err}")
#             st.stop()
 
 
# if token:
#     try:
#         # Store token and name in localStorage
#         # st_javascript(f"sessionStorage.setItem('user_token', '{token}');")
#         st_javascript(f"localStorage.setItem('user_token', '{token}');")
#         decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
#         name = decoded.get("name", "Unknown User")
#         # st_javascript(f"sessionStorage.setItem('user_name', '{name}');")
#         st_javascript(f"localStorage.setItem('user_name', '{name}');")
#         email = decoded.get("email", "No Email")
#         st_javascript(f"localStorage.setItem('user_email', '{email}');")
#         # Set session state
#         st.session_state.user_name = name
#         st.session_state.user_email = email
#         st.session_state.premium_user = True
 
#         # Redirect after 1 second
#         st.title("Authenticating...")
#         st.markdown("""<meta http-equiv='refresh' content='1; url=/' />""", unsafe_allow_html=True)
#         st.stop()
 
#     except ExpiredSignatureError:
#         st.error("Session expired. Please login again.")
#         st.stop()
#     except InvalidTokenError:
#         st.error("Invalid token. Please login again.")
#         # st.stop()
 
# else:
#     # AWS S3 Configuration
#     S3_BUCKET = "chatbotbucket-12345"
#     s3_client = boto3.client("s3")
   
#     os.environ["STREAMLIT_WATCH_FILE"] = "false"
   
#     name = "Unknown User"  
 
#     # Try getting token and name from localStorage
#     # token_js = st_javascript("await sessionStorage.getItem('user_token');")
#     # name_js  = st_javascript("await sessionStorage.getItem('user_name');")
#     token_js = st_javascript("await localStorage.getItem('user_token');")
#     name_js = st_javascript("await localStorage.getItem('user_name');")
#     # if not token and not token_js:
#     if not token and not token_js and not st.session_state.get("payment_processed", False):
#         st.error("🔒 Unauthorized. Please log in on the original tab to continue. Link for Login :- http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/login?DomainPath=/document-chatbot")
#         st.stop()
#     if token_js:
#         try:
#             print(type(SECRET_KEY))
#             decoded = jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"])
#             name = decoded.get("name", name_js or "Unknown User")
#             st.session_state.user_name = name
#             st.session_state.user_email = decoded.get("email", "No Email")
#         except ExpiredSignatureError:
#             st.error("Session expired. Please login again.")
#             st.stop()
#         except InvalidTokenError:
#             st.error("Invalid token. Please login again.")
#             st.stop()
#     else:
       
#         if name_js:
#             st.session_state.user_name = name_js
#             name = name_js
   
#     print(name)
#     required_session_keys = {
#         "user_name": name,
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
 
#     with open(logo_path, "rb") as image_file:
#         encoded_logo = base64.b64encode(image_file.read()).decode()
 
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
#             <meta http-equiv="refresh" content="0; url=http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/our-solutions" />
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
#         st.session_state.premium_user = False
#     if "signed_out" not in st.session_state:
#         st.session_state.signed_out = False
 
 
#     st.markdown('<div class="chat-container">', unsafe_allow_html=True)
 
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
#                 {"<span style='color: black; background-color: #FFFFFF; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
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
#             # clear the per-tab token
#             st_javascript("sessionStorage.clear();")
#             st.session_state.signed_out = True
#             st.rerun()
 
#         st.markdown("---")
   
#         # if st.button("💳 Subscribe"):
#         #     js = """
#         #         <script>
#         #         const token = localStorage.getItem('user_token');
#         #         if (!token) {
#         #             alert("No token found—please log in again.");
#         #         } else {
#         #             const params = new URLSearchParams({
#         #             app_id: "document-chatbot",
#         #             token: token
#         #             });
#         #             window.open(
#         #             "http://paymentdocumentchatbot.s3-website.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html?" + params.toString()
#         #             );
#         #         }
#         #         </script>
#         #     """
#         #     components.html(js, height=0, scrolling=False)
#         if st.button("💳 Subscribe"):
#             js = """
#                 <script>
#                 const token = localStorage.getItem('user_token');
#                 if (!token) {
#                     alert("No token found—please log in again.");
#                 } else {
#                     const params = new URLSearchParams({
#                     app_id: "document-chatbot",
#                     token: token
#                     });
#                     window.open(
#                     "http://127.0.0.1:5500/chatbot/razorpay-payment.html?" + params.toString()
#                     );
#                 }
#                 </script>
#             """
#             components.html(js, height=0, scrolling=False)
#         # if st.button("💳 Subscribe"):
#         #     js = """
#         #         <script>
#         #         const token = localStorage.getItem('user_token');
#         #         if (!token) {
#         #             alert("No token found—please log in again.");
#         #         }
#         #         else {
#         #             const params = new URLSearchParams({
#         #             app_id: "document-chatbot",
#         #             token: token
#         #             });
#         #             window.open(
#         #             "http://127.0.0.1:5500/chatbot/razorpay-payment.html?" + params.toString(),
#         #             "_self"
#         #             );
#         #         }
#         #         </script>
#         #     """
#         #     components.html(js, height=0, scrolling=False)
#         # if st.button("💳 Subscribe", key="subscribe_btn"):
#         #     app_id = "document-chatbot"
#         #     # this component needs its own key
#         #     print("called tille app_id")
#         #     print(token_js)
#         #     print("called till token")
#         #     # build the redirect URL
#         #     redirect_url = (
#         #         "http://127.0.0.1:5500/chatbot/razorpay-payment.html"
#         #         f"?app_id={app_id}&token={token_js}"
#         #     )
 
#         #     # now inject *that* meta-refresh as a component with a unique key
#         #     components.html(
#         #         f"<meta http-equiv='refresh' content='0; url={redirect_url}' />",
#         #         height=0,
#         #         key="payment_meta_refresh"
#         #     )
#         #     st.stop()
#         # if st.button("💳 Subscribe", key="subscribe_btn"):
#         #     app_id = "document-chatbot"
#         #     print(app_id)
#         #     if not token_js:
#         #         st.error("🔒 No token found—please log in first.")
#         #         st.stop()
#         #     print(token_js)
#         #     redirect_url = (
#         #         "http://127.0.0.1:5500/chatbot/razorpay-payment.html"
#         #         f"?app_id={app_id}&token={token_js}"
#         #     )
#         #     print("redirection called ",redirect_url)
#         #     js = f"""
#         #         <script>
#         #         // navigate the top‐level window
#         #         window.top.location.href = "{redirect_url}";
#         #         </script>
#         #         """
#         #     components.html(js, height=0)
#         #     print("error here")
#         #     st.stop()
#         # if st.button("💳 Subscribe"):
#         #     app_id = "document-chatbot"
#         #     print(token_js)
#         #     if not token_js:
#         #         st.error("🔒 No token found—please log in first.")
#         #         st.stop()
#         #     print("1")
#         #     payment_page = "http://127.0.0.1:5500/chatbot/razorpay-payment.html?"
#         #     redirect_url = f"{payment_page}?app_id={app_id}&token={token_js}"
#         #     print("2")
#         #     print(redirect_url)
#         #     st.markdown(
#         #         f"""
#         #         <script>
#         #             window.location.replace("{redirect_url}");
#         #         </script>
#         #         """,
#         #         unsafe_allow_html=True,
#         #     )
#         #     st.stop()
#         # if st.button("💳 Subscribe"):
#         #     app_id = "document-chatbot"
            
#         #     if not token_js:
#         #         st.error("🔒 No token found—please log in first.")
#         #         st.stop()

#         #     # Correct URL
#         #     payment_page = "https://paymentdocumentchatbot.s3.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html"
#         #     redirect_url = f"{payment_page}?app_id={app_id}&token={token_js}"
#         #     print(redirect_url)
#         #     # JavaScript for redirect in same tab
#         #     js_code = f"""s
#         #     <script>
#         #         window.location.href = "{redirect_url}";
#         #     </script>
#         #     """

#         #     # This triggers the redirection
#         #     components.html(js_code, height=0, scrolling=False)
#         #     st.stop()
       
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
 
 
#     if st.session_state.get("premium_user", False):
#         MAX_QUESTIONS = 20
#     else:
#         MAX_QUESTIONS = 3
 
#     if send_button and text_input.strip():
#         is_premium = st.session_state.get("premium_user", False)
#         if st.session_state["chat_count"] >= MAX_QUESTIONS:
#             limit_message = "🎯 You've reached your question limit."
#             if st.session_state.get("premium_user", False):
#                 limit_message += " Thank you for subscribing! You've reached your 20-question premium quota."
#             else:
#                 limit_message += " To continue, please upgrade to Premium."
 
#             st.session_state.chat_history.append(("AI", limit_message))
#             display_animated_text(limit_message, role="AI")
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

















 
# import streamlit as st
# import os
# import random
# from extract_text import extract_text
# from bedrockapi import query_bedrock
# import base64
# import time
# import streamlit.components.v1 as components
# from streamlit_javascript import st_javascript
# import boto3
# import jwt
# from jwt import ExpiredSignatureError, InvalidTokenError
# from dotenv import load_dotenv
# import os
# import psycopg2
 
# load_dotenv()
 
# STATIC_DIR = "static"
 
# if not os.path.exists(STATIC_DIR):
#     os.makedirs(STATIC_DIR)
 
# SECRET_KEY = os.getenv("SECRET_KEY")
 
 
# query_params = st.query_params
# token = query_params.get("token", "")
 
# payment_success = st.query_params.get("payment", "")
# txn_id = st.query_params.get("transaction_id", "")
# name = st.query_params.get("name", "")
# email = st.query_params.get("email", "")
# phone = st.query_params.get("phone", "")
# app_id = st.query_params.get("app_id", "document-chatbot")
# order_id = txn_id  
 
# if "payment_processed" not in st.session_state:            
#     st.session_state.payment_processed = False
 
# if payment_success == "success" and txn_id and not st.session_state.payment_processed:
#     try:
#         print("in payment success try")
#         conn = psycopg2.connect(
#             host=os.getenv("DB_HOST"),
#             user=os.getenv("DB_USER"),
#             password=os.getenv("DB_PASSWORD"),
#             dbname=os.getenv("DB_NAME")
#         )
#         cursor = conn.cursor()
#         insert_query = """
#             INSERT INTO bbt_tempusers(name, email, phone, app_id, order_id)
#             VALUES (%s, %s, %s, %s, %s)
#         """
#         cursor.execute(insert_query, (name, email, phone, app_id, order_id))
#         conn.commit()
#         conn.close()
#         print("Data stored in db")
#         st.session_state.user_name = name
#         st.session_state.premium_user = True
#         st.session_state.payment_processed = True  
#         st.success("✅ Payment successful. Premium features unlocked!")
#         st_javascript(f"localStorage.setItem('user_token','{token}');")
#         st_javascript(f"localStorage.setItem('user_name','{name}');")
#         st_javascript("window.history.replaceState({}, document.title, window.location.pathname);")
#         # st.markdown("""<meta http-equiv='refresh' content='1; url=/?payment=success' />""", unsafe_allow_html=True)
#         st.rerun()
       
#     except psycopg2.Error as err:
#         st.error(f"❌ Database error: {err}")
#         st.stop()
       
#     # redirect_url = f"/payment=success"
#     # st.markdown(
#     #     f"<meta http-equiv='refresh' content='0; url={redirect_url}' />",
#     #     unsafe_allow_html=True
#     # )
#     # st.stop()
 
# print ("token",token) 
# if token:
#     try:
#         # Store token and name in localStorage
#         # st_javascript(f"sessionStorage.setItem('user_token', '{token}');")
#         print("if token try")
#         st_javascript(f"localStorage.setItem('user_token', '{token}');")
#         decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
#         name = decoded.get("name", "Unknown User")
#         # st_javascript(f"sessionStorage.setItem('user_name', '{name}');")
#         st_javascript(f"localStorage.setItem('user_name', '{name}');")
#         email = decoded.get("email", "No Email")
#         st_javascript(f"localStorage.setItem('user_email', '{email}');")
#         # Set session state
#         st.session_state.user_name = name
#         st.session_state.user_email = email
#         st.session_state.premium_user = True
 
#         # Redirect after 1 second
#         st.title("Authenticating...")
#         st.markdown("""<meta http-equiv='refresh' content='1; url=/' />""", unsafe_allow_html=True)
#         st.stop()
#     except ExpiredSignatureError:
#         print("session expired")
#         st.error("Session expired. Please login again.")
#         st.stop()
#     except InvalidTokenError:
#         print("invalid token")
#         st.error("Invalid token. Please login again.")
#         st.stop()
 
# else:
#     print("token in else",token)
#     # AWS S3 Configuration
#     S3_BUCKET = "chatbotbucket-12345"
#     s3_client = boto3.client("s3")
   
#     os.environ["STREAMLIT_WATCH_FILE"] = "false"
   
#     st.set_page_config(page_title="Document Chatbot")
#     print("2")
   
#     name = "Unknown User"  
 
#     # Try getting token and name from localStorage
#     # token_js = st_javascript("await sessionStorage.getItem('user_token');")
#     # name_js  = st_javascript("await sessionStorage.getItem('user_name');")
#     token_js = st_javascript("await localStorage.getItem('user_token');")
#     name_js = st_javascript("await localStorage.getItem('user_name');")
#     print('tokenJS',token_js)
#     # if not token and not token_js:
#     if not token and not token_js and not st.session_state.get("payment_processed", False):
#         st.error("🔒 Unauthorized. Please log in on the original tab to continue. Link for Login :- http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/login?DomainPath=/document-chatbot")
#         st.stop()
#     if token_js:
#         try:
#             print(type(SECRET_KEY))
#             print("token_js",token_js)
#             print("SECRET_KEY",SECRET_KEY)
#             decoded = jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"])
#             print("decoded",jwt.decode(token_js, SECRET_KEY, algorithms=["HS256"]))
#             name = decoded.get("name", name_js or "Unknown User")
#             print("1234")
#             st.session_state.user_name = name
#             print("12345")
#             st.session_state.user_email = decoded.get("email", "No Email")
#             print("123456")
#         except ExpiredSignatureError:
#             st.error("Session expired. Please login again.")
#             st.stop()
#         except InvalidTokenError:
#             st.error("Invalid token. Please login again.")
#             st.stop()
#     else:
       
#         if name_js:
#             st.session_state.user_name = name_js
#             name = name_js
   
#     print(name)
#     required_session_keys = {
#         "user_name": name,
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
 
#     with open(logo_path, "rb") as image_file:
#         encoded_logo = base64.b64encode(image_file.read()).decode()
 
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
#             <meta http-equiv="refresh" content="0; url=http://bellblaze-dev.s3-website.ap-south-1.amazonaws.com/our-solutions" />
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
#         st.session_state.premium_user = False
#         # Initialize important session variables early
#     # if "user_name" not in st.session_state:
#     #     st.error("🔒 Unauthorized. Please log in to access this page.")
#     #     st.stop()
#     if "signed_out" not in st.session_state:
#         st.session_state.signed_out = False
 
 
#     st.markdown('<div class="chat-container">', unsafe_allow_html=True)
 
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
#                 {"<span style='color: black; background-color: #FFFFFF; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;'>⭐ Premium</span>" if st.session_state.get("premium_user", False) else ""}
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
#             # clear the per-tab token
#             st_javascript("sessionStorage.clear();")
#             st.session_state.signed_out = True
#             st.rerun()
 
#         st.markdown("---")
   
#         # if st.button("💳 Subscribe"):
#         #     js = """
#         #         <script>
#         #         const token = localStorage.getItem('user_token');
#         #         if (!token) {
#         #             alert("No token found—please log in again.");
#         #         } else {
#         #             const params = new URLSearchParams({
#         #             app_id: "document-chatbot",
#         #             token: token
#         #             });
#         #             window.open(
#         #             "http://paymentdocumentchatbot.s3-website.ap-south-1.amazonaws.com/razorpay-payment/razorpay-payment.html?" + params.toString()
#         #             );
#         #         }
#         #         </script>
#         #     """
#         #     components.html(js, height=0, scrolling=False)
#         # if st.button("💳 Subscribe"):
#         #     js = """
#         #         <script>
#         #         const token = localStorage.getItem('user_token');
#         #         if (!token) {
#         #             alert("No token found—please log in again.");
#         #         }
#         #         else {
#         #             const params = new URLSearchParams({
#         #             app_id: "document-chatbot",
#         #             token: token
#         #             });
#         #             window.open(
#         #             "http://127.0.0.1:5500/chatbot/razorpay-payment.html?" + params.toString(),
#         #             "_self"
#         #             );
#         #         }
#         #         </script>
#         #     """
#         #     components.html(js, height=0, scrolling=False)
#         # if st.button("💳 Subscribe", key="subscribe_btn"):
#         #     app_id = "document-chatbot"
#         #     # this component needs its own key
#         #     print("called tille app_id")
#         #     print(token_js)
#         #     print("called till token")
#         #     # build the redirect URL
#         #     redirect_url = (
#         #         "http://127.0.0.1:5500/chatbot/razorpay-payment.html"
#         #         f"?app_id={app_id}&token={token_js}"
#         #     )
 
#         #     # now inject *that* meta-refresh as a component with a unique key
#         #     components.html(
#         #         f"<meta http-equiv='refresh' content='0; url={redirect_url}' />",
#         #         height=0,
#         #         key="payment_meta_refresh"
#         #     )
#         #     st.stop()
#         # if st.button("💳 Subscribe", key="subscribe_btn"):
#         #     app_id = "document-chatbot"
#         #     print(app_id)
#         #     if not token_js:
#         #         st.error("🔒 No token found—please log in first.")
#         #         st.stop()
#         #     print(token_js)
#         #     redirect_url = (
#         #         "http://127.0.0.1:5500/chatbot/razorpay-payment.html"
#         #         f"?app_id={app_id}&token={token_js}"
#         #     )
#         #     print("redirection called ",redirect_url)
#         #     js = f"""
#         #         <script>
#         #         // navigate the top‐level window
#         #         window.top.location.href = "{redirect_url}";
#         #         </script>
#         #         """
#         #     components.html(js, height=0)
#         #     print("error here")
#         #     st.stop()
#         if st.button("💳 Subscribe"):
#             js = """
#                 <script>
#                 const token = localStorage.getItem('user_token');
#                 if (!token) {
#                     alert("No token found—please log in again.");
#                 } else {
#                     const params = new URLSearchParams({
#                     app_id: "document-chatbot",
#                     token: token
#                     });
#                     window.open(
#                     "http://127.0.0.1:5500/chatbot/razorpay-payment.html?" + params.toString()
#                     );
#                 }
#                 </script>
#             """
#             components.html(js, height=0, scrolling=False)
       
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
 
 
#     if st.session_state.get("premium_user", False):
#         MAX_QUESTIONS = 20
#     else:
#         MAX_QUESTIONS = 3
 
#     if send_button and text_input.strip():
#         is_premium = st.session_state.get("premium_user", False)
#         if st.session_state["chat_count"] >= MAX_QUESTIONS:
#             limit_message = "🎯 You've reached your question limit."
#             if st.session_state.get("premium_user", False):
#                 limit_message += " Thank you for subscribing! You've reached your 20-question premium quota."
#             else:
#                 limit_message += " To continue, please upgrade to Premium."
 
#             st.session_state.chat_history.append(("AI", limit_message))
#             display_animated_text(limit_message, role="AI")
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
 
