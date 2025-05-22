import razorpay
import hmac
import hashlib
import time
import logging
import streamlit as st
import os
from auth import update_user_in_db
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
# Set up logging
logger = logging.getLogger(__name__)

# Add this after the imports to read and render the HTML template
def render_payment_html():
    """
    Read the payment.html template and return it directly
    """
    try:
        with open("payment.html", "r") as f:
            html_content = f.read()
        return html_content
    except Exception as e:
        logger.error(f"Error rendering payment HTML: {e}")
        return f"""
        <div style="padding: 20px; background-color: #f8f9fa; border-radius: 10px; text-align: center;">
            <h3>Payment Page Error</h3>
            <p>Error loading payment page: {str(e)}</p>
            <p>Please try using one of the other payment methods.</p>
        </div>
        """

class RazorpayPayment:
    def __init__(self, key_id, key_secret, amount, currency, company_name, description):
        """
        Initialize Razorpay payment handler
        
        Parameters:
        -----------
        key_id : str
            Razorpay API Key ID
        key_secret : str
            Razorpay API Key Secret
        amount : int
            Amount in smallest currency unit (paise for INR)
        currency : str
            Currency code (e.g., 'INR')
        company_name : str
            Name of the company to display on checkout page
        description : str
            Description of the payment
        """
        self.key_id = key_id
        self.key_secret = key_secret
        self.amount = amount
        self.currency = currency
        self.company_name = company_name
        self.description = description
        self.client = razorpay.Client(auth=(key_id, key_secret))
    
    def create_order(self, user_id="guest"):
        """
        Create a Razorpay order
        
        Parameters:
        -----------
        user_id : str, optional
            User ID to associate with the order
            
        Returns:
        --------
        dict
            Order details including order_id
        """
        try:
            order_data = {
                "amount": self.amount,
                "currency": self.currency,
                "receipt": f"receipt_{int(time.time())}",
                "payment_capture": 1,  # auto capture
                "notes": {
                    "user_id": user_id
                }
            }
            
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {str(e)}")
            raise
    
    def get_checkout_html(self, order_id):
        """
        Generate HTML for Razorpay checkout
        
        Parameters:
        -----------
        order_id : str
            Razorpay Order ID
            
        Returns:
        --------
        str
            HTML code for Razorpay checkout button
        """
        # Get the current URL for redirection after payment
        # Create a JSON string for the options object to pass to the new window
        options_json = f"""{{
            "key": "{self.key_id}",
            "amount": "{self.amount}",
            "currency": "{self.currency}",
            "name": "{self.company_name}",
            "description": "{self.description}",
            "order_id": "{order_id}",
            "prefill": {{
                "name": "",
                "email": "",
                "contact": ""
            }},
            "theme": {{
                "color": "#17a7e0"
            }}
        }}"""
        
        return f"""
        <div id="razorpay-button" style="text-align: center; margin: 10px 0;">
            <style>
                .payment-button {{
                    display: inline-block;
                    background-color: #17a7e0;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: bold;
                    cursor: pointer;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    text-decoration: none;
                    width: 100%;
                    text-align: center;
                    transition: background-color 0.3s ease;
                }}
                .payment-button:hover {{
                    background-color: #1490c2;  /* A slightly darker blue, not red */
                }}
            </style>
            <a id="rzp-button" href="javascript:void(0);" class="payment-button">
                💎 Make Payment (₹{self.amount/100})
            </a>
            <div style="font-size: 12px; color: #666; margin-top: 5px;">Opens in a new tab</div>
        </div>
        <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
        <script>
            // Store the current window location to redirect back after payment
            const currentLocation = window.location.href;
            
            // Options for Razorpay
            const options = {options_json};
            
            document.getElementById('rzp-button').onclick = function(e) {{
                e.preventDefault();
                
                // Serialize options to pass to the new window
                const optionsString = JSON.stringify(options);
                const currentUrl = currentLocation;
                
                // Open payment gateway directly in a new tab/window
                const newWindow = window.open('', '_blank');
                if (newWindow) {{
                    newWindow.document.write(`
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>Payment Gateway</title>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <style>
                                body {{
                                    display: flex;
                                    justify-content: center;
                                    align-items: center;
                                    height: 100vh;
                                    font-family: Arial, sans-serif;
                                    margin: 0;
                                    background-color: #f9f9f9;
                                }}
                                .loader {{
                                    border: 5px solid #f3f3f3;
                                    border-radius: 50%;
                                    border-top: 5px solid #17a7e0;
                                    width: 50px;
                                    height: 50px;
                                    animation: spin 1s linear infinite;
                                }}
                                @keyframes spin {{
                                    0% {{ transform: rotate(0deg); }}
                                    100% {{ transform: rotate(360deg); }}
                                }}
                                .container {{
                                    text-align: center;
                                }}
                            </style>
                            <script src="https://checkout.razorpay.com/v1/checkout.js"><\/script>
                        </head>
                        <body>
                            <div class="container">
                                <div class="loader"></div>
                                <p>Loading payment gateway...</p>
                            </div>
                            <script>
                                // Parse the options passed from the parent window
                                const optionsData = ${{optionsString}};
                                
                                // The redirect URL to return to after payment
                                const returnUrl = "${{currentUrl}}";
                                
                                // Setup Razorpay checkout
                                document.addEventListener('DOMContentLoaded', function() {{
                                    const rzp_options = optionsData;
                                    rzp_options.handler = function(response) {{
                                        // Store payment info for the parent window
                                        localStorage.setItem('razorpay_payment_id', response.razorpay_payment_id);
                                        localStorage.setItem('razorpay_order_id', response.razorpay_order_id);
                                        localStorage.setItem('razorpay_signature', response.razorpay_signature);
                                        
                                        // Close this window and redirect parent to the currentLocation
                                        window.opener.location.href = returnUrl;
                                        window.close();
                                    }};
                                    
                                    const rzp = new Razorpay(rzp_options);
                                    rzp.on('payment.failed', function (response){{
                                        alert('Payment failed. Please try again.');
                                        window.close();
                                    }});
                                    
                                    setTimeout(function() {{
                                        rzp.open();
                                    }}, 1000);
                                }});
                            <\/script>
                        </body>
                        </html>
                    `);
                    newWindow.document.close();
                }} else {{
                    // Fallback if popup is blocked: open in same window
                    alert("Please allow popups for this site to open the payment gateway in a new tab.");
                    const rzp = new Razorpay(options);
                    rzp.open();
                }}
            }};
        </script>
        """
    
    def verify_payment_signature(self, order_id, payment_id, signature):
        """
        Verify Razorpay payment signature
        
        Parameters:
        -----------
        order_id : str
            Razorpay Order ID
        payment_id : str
            Razorpay Payment ID
        signature : str
            Razorpay Signature
            
        Returns:
        --------
        bool
            True if signature is valid, False otherwise
        """
        try:
            # Generate the signature verification data
            msg = f"{order_id}|{payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode(),
                msg.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Verify the signature
            return hmac.compare_digest(generated_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying payment signature: {str(e)}")
            return False
    
    def check_payment_status(self, payment_id):
        """
        Check payment status
        
        Parameters:
        -----------
        payment_id : str
            Razorpay Payment ID
            
        Returns:
        --------
        dict
            Payment details including status
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            raise

def display_payment_interface(razorpay_payment):
    """
    Display the Razorpay payment interface
    
    Parameters:
    -----------
    razorpay_payment : RazorpayPayment
        RazorpayPayment instance with payment details
    """
    try:
        st.title("Upgrade to Premium")
        
        # Add benefits section for premium users
        st.markdown("""
        ### Premium Benefits:
        
        - ✅ **Unlimited forecasting** - No more usage limits
        - ✅ **Priority support** - Get faster responses to your queries
        - ✅ **Advanced forecasting models** - Access to more sophisticated models
        - ✅ **Unlimited file uploads** - No file size or number restrictions
        - ✅ **Enhanced visualizations** - Get more detailed and interactive charts
        """)
        
        # Display payment options
        st.markdown("### Payment Options")
        
        # Method 1: Use the HTML file directly
        redirect_url = os.getenv("REDIRECT_URL", "https://data-forecast-chatbot.s3.ap-south-1.amazonaws.com/payment.html")  #s3 link
        st.markdown(
            f"""
            <a href="{redirect_url}/payment.html" target="_blank">
                <button style="
                    background-color: #17a7e0;
                    color: white;
                    border: none;
                    width: 100%;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 10px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                ">
                    Open Payment Page
                </button>
            </a>
            """, unsafe_allow_html=True
        )
        
        st.markdown(
            """
            <a href="https://data-forecast-chatbot.s3.ap-south-1.amazonaws.com/payment.html" target="_blank">    
                <button style="
                    background-color: #17a7e0;
                    color: white;
                    border: none;
                    width: 100%;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 10px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                ">
                    Open Razorpay HTML
                </button>
            </a>
            """, unsafe_allow_html=True
        )
        
        # Method 2: Inline payment form
        with st.expander("Or pay directly here"):
            # Create order for direct payment
            order = razorpay_payment.create_order(st.session_state.username)
            
            # Display payment button
            payment_html = razorpay_payment.get_checkout_html(order["id"])
            st.components.v1.html(payment_html, height=150)
            
            # Add option to use our custom HTML template
            st.markdown("---")
            st.markdown("### Alternative Payment Method")
            
            # Render the payment HTML template
            st.components.v1.html(render_payment_html(), height=450)
        
        # Back button to return to main app
        if st.button("← Back to App"):
            st.session_state.show_payment_page = False
            st.rerun()
    except Exception as e:
        st.error(f"Error displaying payment interface: {str(e)}")
    
    # Create order if not already created
    if "razorpay_order_id" not in st.session_state:
        try:
            user_id = st.session_state.username if "username" in st.session_state else "guest"
            order = razorpay_payment.create_order(user_id)
            st.session_state.razorpay_order_id = order['id']
        except Exception as e:
            st.error(f"Failed to create Razorpay order: {str(e)}")
    
    # Initialize payment verification status
    if "payment_verified" not in st.session_state:
        st.session_state.payment_verified = False
    
    # Initialize payment initiated flag
    if "payment_initiated" not in st.session_state:
        st.session_state.payment_initiated = False
    
    # Get payment details from query params
    payment_id = st.query_params.get_all("razorpay_payment_id")[0] if "razorpay_payment_id" in st.query_params else None
    order_id = st.query_params.get_all("razorpay_order_id")[0] if "razorpay_order_id" in st.query_params else None
    signature = st.query_params.get_all("razorpay_signature")[0] if "razorpay_signature" in st.query_params else None
    payment_verified = st.session_state.payment_verified
    
    # Handle successful payment if we have payment details
    if payment_id and order_id and signature and not payment_verified:
        # Verify payment
        is_valid = razorpay_payment.verify_payment_signature(order_id, payment_id, signature)
        
        if is_valid:
            # Mark payment as verified
            payment_verified = True
            st.session_state.payment_verified = True
            st.session_state.paid_user = True
            
            # Make sure the premium status is saved to the database
            try:
                # Save premium status to database
                logger.info("Payment verified. Updating user to premium status.")
                update_user_in_db()                
        
                # Load environment variables
                load_dotenv()
                
                # Get database connection details
                DB_USER = os.getenv('DB_USER', 'postgres')
                DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
                DB_HOST = os.getenv('DB_HOST', 'localhost')
                DB_PORT = os.getenv('DB_PORT', '5432')
                DB_NAME = os.getenv('DB_NAME', 'postgres2')
                
                # Create engine and check user status
                DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                engine = create_engine(DATABASE_URL)
                with engine.connect() as connection:
                    username = st.session_state.username if "username" in st.session_state else "default_user"
                    result = connection.execute(text(
                        "SELECT paid_user FROM users WHERE username = :username"
                    ), {"username": username})
                    
                    user = result.fetchone()
                    if user and user.paid_user != 1:
                        # If update didn't work through normal channels, force it directly
                        logger.warning("Premium status not updated. Forcing update directly.")
                        connection.execute(text(
                            "UPDATE users SET paid_user = 1 WHERE username = :username"
                        ), {"username": username})
                        connection.commit()
                        logger.info("Premium status updated directly in database.")
            except Exception as e:
                logger.error(f"Error updating premium status: {e}")
            
            # Show success message
            st.success("✅ Payment verified successfully! You now have premium access.")
            st.balloons()
            
            return True
    
    # Script to check for payment completion in localStorage (for redirected sessions)
    payment_check_script = """
    <script>
        // Function to check for payment info in localStorage
        function checkForPayment() {
            if (localStorage.getItem('razorpay_payment_id')) {
                // We have payment info, log it for debugging
                console.log("Found payment info in localStorage");
                console.log("Payment ID:", localStorage.getItem('razorpay_payment_id'));
                console.log("Order ID:", localStorage.getItem('razorpay_order_id'));
                
                // Send to Streamlit
                window.parent.postMessage({
                    type: 'razorpay_payment',
                    payment_id: localStorage.getItem('razorpay_payment_id'),
                    order_id: localStorage.getItem('razorpay_order_id'),
                    signature: localStorage.getItem('razorpay_signature')
                }, "*");
                
                // Clear localStorage
                localStorage.removeItem('razorpay_payment_id');
                localStorage.removeItem('razorpay_order_id');
                localStorage.removeItem('razorpay_signature');
                
                // Automatically click the "I've Completed Payment" button
                setTimeout(function() {
                    const paymentCompletedButton = document.querySelector('button[data-testid="baseButton-secondary"]');
                    if (paymentCompletedButton) {
                        console.log("Clicking payment completed button");
                        paymentCompletedButton.click();
                    } else {
                        console.log("Payment button not found");
                    }
                }, 1000);
                
                return true;
            }
            return false;
        }
        
        // Check immediately and then every second for a short period
        if (!checkForPayment()) {
            let checkCount = 0;
            const intervalId = setInterval(function() {
                if (checkForPayment() || checkCount > 5) {
                    clearInterval(intervalId);
                }
                checkCount++;
            }, 1000);
        }
    </script>
    """
    
    # Insert the script to check for payment in localStorage
    st.components.v1.html(payment_check_script, height=0)
    
    # Display Razorpay checkout button if not verified yet
    if not st.session_state.payment_verified:
        if "razorpay_order_id" in st.session_state:
            razorpay_html = razorpay_payment.get_checkout_html(st.session_state.razorpay_order_id)
            st.components.v1.html(razorpay_html, height=150)
    
    # Automatically update UI when payment is verified (triggered by localStorage check)
    if st.session_state.payment_verified:
        st.session_state.paid_user = True
        st.session_state.show_payment_page = False
        
        # Make sure the premium status is saved to the database
        try:
            # Save premium status to database
            logger.info("Payment verified. Updating user to premium status (auto-update).")
            update_user_in_db()
            # Double-check that the update was successful
            from sqlalchemy import create_engine, text
            import os
            from dotenv import load_dotenv
            
            # Load environment variables
            load_dotenv()
            
            # Get database connection details
            DB_USER = os.getenv('DB_USER', 'postgres')
            DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
            DB_HOST = os.getenv('DB_HOST', 'localhost')
            DB_PORT = os.getenv('DB_PORT', '5432')
            DB_NAME = os.getenv('DB_NAME', 'postgres2')
            
            # Create engine and check user status
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            engine = create_engine(DATABASE_URL)
            with engine.connect() as connection:
                username = st.session_state.username if "username" in st.session_state else "default_user"
                result = connection.execute(text(
                    "SELECT paid_user FROM users WHERE username = :username"
                ), {"username": username})
                
                user = result.fetchone()
                if user and user.paid_user != 1:
                    # If update didn't work through normal channels, force it directly
                    logger.warning("Premium status not updated in auto-update. Forcing update directly.")
                    connection.execute(text(
                        "UPDATE users SET paid_user = 1 WHERE username = :username"
                    ), {"username": username})
                    connection.commit()
                    logger.info("Premium status updated directly in database (auto-update).")
        except Exception as e:
            logger.error(f"Error updating premium status in auto-update: {e}")
        
        st.success("🎉 Payment verified!")
        st.rerun()
    
    # Return whether payment is verified
    return st.session_state.payment_verified 


# =====================================================================

# import razorpay
# import hmac
# import hashlib
# import time
# import logging
# import streamlit as st
# import os
# from auth import update_user_in_db
# from sqlalchemy import create_engine, text
# import os
# from dotenv import load_dotenv
# # Set up logging
# logger = logging.getLogger(__name__)

# # Add this after the imports to read and render the HTML template
# def render_payment_html():
#     """
#     Read the payment.html template and return it directly
#     """
#     try:
#         with open("payment.html", "r") as f:
#             html_content = f.read()
#         return html_content
#     except Exception as e:
#         logger.error(f"Error rendering payment HTML: {e}")
#         return f"""
#         <div style="padding: 20px; background-color: #f8f9fa; border-radius: 10px; text-align: center;">
#             <h3>Payment Page Error</h3>
#             <p>Error loading payment page: {str(e)}</p>
#             <p>Please try using one of the other payment methods.</p>
#         </div>
#         """

# class RazorpayPayment:
#     def __init__(self, key_id, key_secret, amount, currency, company_name, description):
#         """
#         Initialize Razorpay payment handler
        
#         Parameters:
#         -----------
#         key_id : str
#             Razorpay API Key ID
#         key_secret : str
#             Razorpay API Key Secret
#         amount : int
#             Amount in smallest currency unit (paise for INR)
#         currency : str
#             Currency code (e.g., 'INR')
#         company_name : str
#             Name of the company to display on checkout page
#         description : str
#             Description of the payment
#         """
#         self.key_id = key_id
#         self.key_secret = key_secret
#         self.amount = amount
#         self.currency = currency
#         self.company_name = company_name
#         self.description = description
#         self.client = razorpay.Client(auth=(key_id, key_secret))
    
#     def create_order(self, user_id="guest"):
#         """
#         Create a Razorpay order
        
#         Parameters:
#         -----------
#         user_id : str, optional
#             User ID to associate with the order
            
#         Returns:
#         --------
#         dict
#             Order details including order_id
#         """
#         try:
#             order_data = {
#                 "amount": self.amount,
#                 "currency": self.currency,
#                 "receipt": f"receipt_{int(time.time())}",
#                 "payment_capture": 1,  # auto capture
#                 "notes": {
#                     "user_id": user_id
#                 }
#             }
            
#             order = self.client.order.create(data=order_data)
#             logger.info(f"Razorpay order created: {order['id']}")
#             return order
#         except Exception as e:
#             logger.error(f"Error creating Razorpay order: {str(e)}")
#             raise
    
#     def get_checkout_html(self, order_id):
#         """
#         Generate HTML for Razorpay checkout
        
#         Parameters:
#         -----------
#         order_id : str
#             Razorpay Order ID
            
#         Returns:
#         --------
#         str
#             HTML code for Razorpay checkout button
#         """
#         # Get the current URL for redirection after payment
#         # Create a JSON string for the options object to pass to the new window
#         options_json = f"""{{
#             "key": "{self.key_id}",
#             "amount": "{self.amount}",
#             "currency": "{self.currency}",
#             "name": "{self.company_name}",
#             "description": "{self.description}",
#             "order_id": "{order_id}",
#             "prefill": {{
#                 "name": "",
#                 "email": "",
#                 "contact": ""
#             }},
#             "theme": {{
#                 "color": "#17a7e0"
#             }}
#         }}"""
        
#         return f"""
#         <div id="razorpay-button" style="text-align: center; margin: 10px 0;">
#             <style>
#                 .payment-button {{
#                     display: inline-block;
#                     background-color: #17a7e0;
#                     color: white;
#                     padding: 8px 16px;
#                     border: none;
#                     border-radius: 4px;
#                     font-size: 14px;
#                     font-weight: bold;
#                     cursor: pointer;
#                     box-shadow: 0 2px 5px rgba(0,0,0,0.2);
#                     text-decoration: none;
#                     width: 100%;
#                     text-align: center;
#                     transition: background-color 0.3s ease;
#                 }}
#                 .payment-button:hover {{
#                     background-color: #1490c2;  /* A slightly darker blue, not red */
#                 }}
#             </style>
#             <a id="rzp-button" href="javascript:void(0);" class="payment-button">
#                 💎 Make Payment (₹{self.amount/100})
#             </a>
#             <div style="font-size: 12px; color: #666; margin-top: 5px;">Opens in a new tab</div>
#         </div>
#         <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
#         <script>
#             // Store the current window location to redirect back after payment
#             const currentLocation = window.location.href;
            
#             // Options for Razorpay
#             const options = {options_json};
            
#             document.getElementById('rzp-button').onclick = function(e) {{
#                 e.preventDefault();
                
#                 // Serialize options to pass to the new window
#                 const optionsString = JSON.stringify(options);
#                 const currentUrl = currentLocation;
                
#                 // Open payment gateway directly in a new tab/window
#                 const newWindow = window.open('', '_blank');
#                 if (newWindow) {{
#                     newWindow.document.write(`
#                         <!DOCTYPE html>
#                         <html>
#                         <head>
#                             <title>Payment Gateway</title>
#                             <meta name="viewport" content="width=device-width, initial-scale=1">
#                             <style>
#                                 body {{
#                                     display: flex;
#                                     justify-content: center;
#                                     align-items: center;
#                                     height: 100vh;
#                                     font-family: Arial, sans-serif;
#                                     margin: 0;
#                                     background-color: #f9f9f9;
#                                 }}
#                                 .loader {{
#                                     border: 5px solid #f3f3f3;
#                                     border-radius: 50%;
#                                     border-top: 5px solid #17a7e0;
#                                     width: 50px;
#                                     height: 50px;
#                                     animation: spin 1s linear infinite;
#                                 }}
#                                 @keyframes spin {{
#                                     0% {{ transform: rotate(0deg); }}
#                                     100% {{ transform: rotate(360deg); }}
#                                 }}
#                                 .container {{
#                                     text-align: center;
#                                 }}
#                             </style>
#                             <script src="https://checkout.razorpay.com/v1/checkout.js"><\/script>
#                         </head>
#                         <body>
#                             <div class="container">
#                                 <div class="loader"></div>
#                                 <p>Loading payment gateway...</p>
#                             </div>
#                             <script>
#                                 // Parse the options passed from the parent window
#                                 const optionsData = ${{optionsString}};
                                
#                                 // The redirect URL to return to after payment
#                                 const returnUrl = "${{currentUrl}}";
                                
#                                 // Setup Razorpay checkout
#                                 document.addEventListener('DOMContentLoaded', function() {{
#                                     const rzp_options = optionsData;
#                                     rzp_options.handler = function(response) {{
#                                         // Store payment info for the parent window
#                                         localStorage.setItem('razorpay_payment_id', response.razorpay_payment_id);
#                                         localStorage.setItem('razorpay_order_id', response.razorpay_order_id);
#                                         localStorage.setItem('razorpay_signature', response.razorpay_signature);
                                        
#                                         // Close this window and redirect parent to the currentLocation
#                                         window.opener.location.href = returnUrl;
#                                         window.close();
#                                     }};
                                    
#                                     const rzp = new Razorpay(rzp_options);
#                                     rzp.on('payment.failed', function (response){{
#                                         alert('Payment failed. Please try again.');
#                                         window.close();
#                                     }});
                                    
#                                     setTimeout(function() {{
#                                         rzp.open();
#                                     }}, 1000);
#                                 }});
#                             <\/script>
#                         </body>
#                         </html>
#                     `);
#                     newWindow.document.close();
#                 }} else {{
#                     // Fallback if popup is blocked: open in same window
#                     alert("Please allow popups for this site to open the payment gateway in a new tab.");
#                     const rzp = new Razorpay(options);
#                     rzp.open();
#                 }}
#             }};
#         </script>
#         """
    
#     def verify_payment_signature(self, order_id, payment_id, signature):
#         """
#         Verify Razorpay payment signature
        
#         Parameters:
#         -----------
#         order_id : str
#             Razorpay Order ID
#         payment_id : str
#             Razorpay Payment ID
#         signature : str
#             Razorpay Signature
            
#         Returns:
#         --------
#         bool
#             True if signature is valid, False otherwise
#         """
#         try:
#             # Generate the signature verification data
#             msg = f"{order_id}|{payment_id}"
#             generated_signature = hmac.new(
#                 self.key_secret.encode(),
#                 msg.encode(),
#                 hashlib.sha256
#             ).hexdigest()
            
#             # Verify the signature
#             return hmac.compare_digest(generated_signature, signature)
#         except Exception as e:
#             logger.error(f"Error verifying payment signature: {str(e)}")
#             return False
    
#     def check_payment_status(self, payment_id):
#         """
#         Check payment status
        
#         Parameters:
#         -----------
#         payment_id : str
#             Razorpay Payment ID
            
#         Returns:
#         --------
#         dict
#             Payment details including status
#         """
#         try:
#             payment = self.client.payment.fetch(payment_id)
#             return payment
#         except Exception as e:
#             logger.error(f"Error checking payment status: {str(e)}")
#             raise

# def display_payment_interface(razorpay_payment):
#     """
#     Display the Razorpay payment interface
    
#     Parameters:
#     -----------
#     razorpay_payment : RazorpayPayment
#         RazorpayPayment instance with payment details
#     """
#     try:
#         st.title("Upgrade to Premium")
        
#         # Add benefits section for premium users
#         st.markdown("""
#         ### Premium Benefits:
        
#         - ✅ **Unlimited forecasting** - No more usage limits
#         - ✅ **Priority support** - Get faster responses to your queries
#         - ✅ **Advanced forecasting models** - Access to more sophisticated models
#         - ✅ **Unlimited file uploads** - No file size or number restrictions
#         - ✅ **Enhanced visualizations** - Get more detailed and interactive charts
#         """)
        
#         # Display payment options
#         st.markdown("### Payment Options")
        
#         # Method 1: Use the HTML file directly
#         redirect_url = os.getenv("REDIRECT_URL", "https://dataforecast-html-payment.s3.ap-south-1.amazonaws.com/payment.html")  #s3 link
#         st.markdown(
#             f"""
#             <a href="{redirect_url}/payment.html" target="_blank">
#                 <button style="
#                     background-color: #17a7e0;
#                     color: white;
#                     border: none;
#                     width: 100%;
#                     padding: 15px;
#                     margin-bottom: 20px;
#                     border-radius: 10px;
#                     font-size: 16px;
#                     font-weight: bold;
#                     cursor: pointer;
#                 ">
#                     Open Payment Page
#                 </button>
#             </a>
#             """, unsafe_allow_html=True
#         )
        
#         st.markdown(
#             """
#             <a href="https://dataforecast-html-payment.s3.ap-south-1.amazonaws.com/payment.html" target="_blank">    
#                 <button style="
#                     background-color: #17a7e0;
#                     color: white;
#                     border: none;
#                     width: 100%;
#                     padding: 15px;
#                     margin-bottom: 20px;
#                     border-radius: 10px;
#                     font-size: 16px;
#                     font-weight: bold;
#                     cursor: pointer;
#                 ">
#                     Open Razorpay HTML
#                 </button>
#             </a>
#             """, unsafe_allow_html=True
#         )
        
#         # Method 2: Inline payment form
#         with st.expander("Or pay directly here"):
#             # Create order for direct payment
#             order = razorpay_payment.create_order(st.session_state.username)
            
#             # Display payment button
#             payment_html = razorpay_payment.get_checkout_html(order["id"])
#             st.components.v1.html(payment_html, height=150)
            
#             # Add option to use our custom HTML template
#             st.markdown("---")
#             st.markdown("### Alternative Payment Method")
            
#             # Render the payment HTML template
#             st.components.v1.html(render_payment_html(), height=450)
        
#         # Back button to return to main app
#         if st.button("← Back to App"):
#             st.session_state.show_payment_page = False
#             st.rerun()
#     except Exception as e:
#         st.error(f"Error displaying payment interface: {str(e)}")
    
#     # Create order if not already created
#     if "razorpay_order_id" not in st.session_state:
#         try:
#             user_id = st.session_state.username if "username" in st.session_state else "guest"
#             order = razorpay_payment.create_order(user_id)
#             st.session_state.razorpay_order_id = order['id']
#         except Exception as e:
#             st.error(f"Failed to create Razorpay order: {str(e)}")
    
#     # Initialize payment verification status
#     if "payment_verified" not in st.session_state:
#         st.session_state.payment_verified = False
    
#     # Initialize payment initiated flag
#     if "payment_initiated" not in st.session_state:
#         st.session_state.payment_initiated = False
    
#     # Get payment details from query params
#     payment_id = st.query_params.get_all("razorpay_payment_id")[0] if "razorpay_payment_id" in st.query_params else None
#     order_id = st.query_params.get_all("razorpay_order_id")[0] if "razorpay_order_id" in st.query_params else None
#     signature = st.query_params.get_all("razorpay_signature")[0] if "razorpay_signature" in st.query_params else None
#     payment_verified = st.session_state.payment_verified
    
#     # Handle successful payment if we have payment details
#     if payment_id and order_id and signature and not payment_verified:
#         # Verify payment
#         is_valid = razorpay_payment.verify_payment_signature(order_id, payment_id, signature)
        
#         if is_valid:
#             # Mark payment as verified
#             payment_verified = True
#             st.session_state.payment_verified = True
#             st.session_state.paid_user = True
            
#             # Make sure the premium status is saved to the database
#             try:
#                 # Save premium status to database
#                 logger.info("Payment verified. Updating user to premium status.")
#                 update_user_in_db()                
        
#                 # Load environment variables
#                 load_dotenv()
                
#                 # Get database connection details
#                 DB_USER = os.getenv('DB_USER', 'postgres')
#                 DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
#                 DB_HOST = os.getenv('DB_HOST', 'localhost')
#                 DB_PORT = os.getenv('DB_PORT', '5432')
#                 DB_NAME = os.getenv('DB_NAME', 'postgres2')
                
#                 # Create engine and check user status
#                 DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
#                 engine = create_engine(DATABASE_URL)
#                 with engine.connect() as connection:
#                     username = st.session_state.username if "username" in st.session_state else "default_user"
#                     result = connection.execute(text(
#                         "SELECT paid_user FROM users WHERE username = :username"
#                     ), {"username": username})
                    
#                     user = result.fetchone()
#                     if user and user.paid_user != 1:
#                         # If update didn't work through normal channels, force it directly
#                         logger.warning("Premium status not updated. Forcing update directly.")
#                         connection.execute(text(
#                             "UPDATE users SET paid_user = 1 WHERE username = :username"
#                         ), {"username": username})
#                         connection.commit()
#                         logger.info("Premium status updated directly in database.")
#             except Exception as e:
#                 logger.error(f"Error updating premium status: {e}")
            
#             # Show success message
#             st.success("✅ Payment verified successfully! You now have premium access.")
#             st.balloons()
            
#             return True
    
#     # Script to check for payment completion in localStorage (for redirected sessions)
#     payment_check_script = """
#     <script>
#         // Function to check for payment info in localStorage
#         function checkForPayment() {
#             if (localStorage.getItem('razorpay_payment_id')) {
#                 // We have payment info, log it for debugging
#                 console.log("Found payment info in localStorage");
#                 console.log("Payment ID:", localStorage.getItem('razorpay_payment_id'));
#                 console.log("Order ID:", localStorage.getItem('razorpay_order_id'));
                
#                 // Send to Streamlit
#                 window.parent.postMessage({
#                     type: 'razorpay_payment',
#                     payment_id: localStorage.getItem('razorpay_payment_id'),
#                     order_id: localStorage.getItem('razorpay_order_id'),
#                     signature: localStorage.getItem('razorpay_signature')
#                 }, "*");
                
#                 // Clear localStorage
#                 localStorage.removeItem('razorpay_payment_id');
#                 localStorage.removeItem('razorpay_order_id');
#                 localStorage.removeItem('razorpay_signature');
                
#                 // Automatically click the "I've Completed Payment" button
#                 setTimeout(function() {
#                     const paymentCompletedButton = document.querySelector('button[data-testid="baseButton-secondary"]');
#                     if (paymentCompletedButton) {
#                         console.log("Clicking payment completed button");
#                         paymentCompletedButton.click();
#                     } else {
#                         console.log("Payment button not found");
#                     }
#                 }, 1000);
                
#                 return true;
#             }
#             return false;
#         }
        
#         // Check immediately and then every second for a short period
#         if (!checkForPayment()) {
#             let checkCount = 0;
#             const intervalId = setInterval(function() {
#                 if (checkForPayment() || checkCount > 5) {
#                     clearInterval(intervalId);
#                 }
#                 checkCount++;
#             }, 1000);
#         }
#     </script>
#     """
    
#     # Insert the script to check for payment in localStorage
#     st.components.v1.html(payment_check_script, height=0)
    
#     # Display Razorpay checkout button if not verified yet
#     if not st.session_state.payment_verified:
#         if "razorpay_order_id" in st.session_state:
#             razorpay_html = razorpay_payment.get_checkout_html(st.session_state.razorpay_order_id)
#             st.components.v1.html(razorpay_html, height=150)
    
#     # Automatically update UI when payment is verified (triggered by localStorage check)
#     if st.session_state.payment_verified:
#         st.session_state.paid_user = True
#         st.session_state.show_payment_page = False
        
#         # Make sure the premium status is saved to the database
#         try:
#             # Save premium status to database
#             logger.info("Payment verified. Updating user to premium status (auto-update).")
#             update_user_in_db()
#             # Double-check that the update was successful
#             from sqlalchemy import create_engine, text
#             import os
#             from dotenv import load_dotenv
            
#             # Load environment variables
#             load_dotenv()
            
#             # Get database connection details
#             DB_USER = os.getenv('DB_USER', 'postgres')
#             DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
#             DB_HOST = os.getenv('DB_HOST', 'localhost')
#             DB_PORT = os.getenv('DB_PORT', '5432')
#             DB_NAME = os.getenv('DB_NAME', 'postgres2')
            
#             # Create engine and check user status
#             DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
#             engine = create_engine(DATABASE_URL)
#             with engine.connect() as connection:
#                 username = st.session_state.username if "username" in st.session_state else "default_user"
#                 result = connection.execute(text(
#                     "SELECT paid_user FROM users WHERE username = :username"
#                 ), {"username": username})
                
#                 user = result.fetchone()
#                 if user and user.paid_user != 1:
#                     # If update didn't work through normal channels, force it directly
#                     logger.warning("Premium status not updated in auto-update. Forcing update directly.")
#                     connection.execute(text(
#                         "UPDATE users SET paid_user = 1 WHERE username = :username"
#                     ), {"username": username})
#                     connection.commit()
#                     logger.info("Premium status updated directly in database (auto-update).")
#         except Exception as e:
#             logger.error(f"Error updating premium status in auto-update: {e}")
        
#         st.success("🎉 Payment verified!")
#         st.rerun()
    
#     # Return whether payment is verified
#     return st.session_state.payment_verified 
