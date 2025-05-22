import os
import json
import pickle
import logging
import time
import sys
from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv, find_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = find_dotenv()
if env_path:
    logger.info(f"Found .env file at: {env_path}")
    load_dotenv(env_path)
else:
    logger.warning("No .env file found. Using default values.")

# Get PostgreSQL connection details from environment variables
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres')

# Print connection details (password obscured)
logger.info(f"Database config: USER={DB_USER}, HOST={DB_HOST}, PORT={DB_PORT}, DB={DB_NAME}")

# Create SQLAlchemy engine
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Define database models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    paid_user = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)
    premium_usage_count = Column(Integer, default=0)  # Track premium usage separately
    subscription_expires_at = Column(String(100), nullable=True)  # Store expiration timestamp
    
    # Relationships
    chat_histories = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="user", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="user", cascade="all, delete-orphan")

class ChatHistory(Base):
    __tablename__ = 'chat_histories'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(JSONB, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="chat_histories")

class Forecast(Base):
    __tablename__ = 'forecasts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    data = Column(JSONB, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="forecasts")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='_user_forecast_name_uc'),
    )

class Model(Base):
    __tablename__ = 'models'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    binary_data = Column(LargeBinary, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="models")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='_user_model_name_uc'),
    )

class Transaction(Base):
    __tablename__ = 'bbt_tempusers'
    
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(Integer, nullable=True)
    app_id = Column(String(255), nullable=False)
    order_id = Column(String(255), nullable=False, primary_key=True)
    
    def __repr__(self):
        return f"<Transaction(name={self.name}, email={self.email}, phone={self.phone}, app_id={self.app_id}, order_id={self.order_id})>"

# Function to initialize the database
def initialize_database():
    """Create database tables if they don't exist"""
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

# User data functions
def save_user_data(users_dict):
    """Save user data to PostgreSQL database"""
    session = Session()
    
    try:
        for username, user_data in users_dict.items():
            try:
                # Sanitize username and other values
                sanitized_username = username.strip() if username else "default_user"
                
                # Log the attempt to save
                logger.info(f"Saving data for user: {sanitized_username}")
                
                # Check if user exists
                user = session.query(User).filter_by(username=sanitized_username).first()
                
                if user:
                    # Update existing user
                    logger.info(f"Updating existing user: {sanitized_username}")
                    user.password_hash = user_data.get('password', '')
                    user.email = user_data.get('email', '')
                    user.paid_user = user_data.get('paid_user', 0)
                    user.usage_count = user_data.get('usage_count', 0)
                    user.premium_usage_count = user_data.get('premium_usage_count', 0)
                    user.subscription_expires_at = user_data.get('subscription_expires_at', None)
                else:
                    # Create new user
                    logger.info(f"Creating new user: {sanitized_username}")
                    new_user = User(
                        username=sanitized_username,
                        password_hash=user_data.get('password', ''),
                        email=user_data.get('email', ''),
                        paid_user=user_data.get('paid_user', 0),
                        usage_count=user_data.get('usage_count', 0),
                        premium_usage_count=user_data.get('premium_usage_count', 0),
                        subscription_expires_at=user_data.get('subscription_expires_at', None)
                    )
                    session.add(new_user)
                
                # Try to commit changes for this user
                try:
                    session.commit()
                    logger.info(f"Successfully saved data for user: {sanitized_username}")
                except Exception as user_error:
                    session.rollback()
                    logger.error(f"Error saving specific user {sanitized_username}: {str(user_error)}")
                    # Continue with next user
            except Exception as inner_error:
                logger.error(f"Error processing user entry {username}: {str(inner_error)}")
                # Continue with next user
                
        logger.info("User data save process completed")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error in overall save_user_data process: {str(e)}")
        return False
    finally:
        session.close()

def load_user_data():
    """Load user data from PostgreSQL database"""
    session = Session()
    
    try:
        users = session.query(User).all()
        users_dict = {}
        
        for user in users:
            users_dict[user.username] = {
                'password': user.password_hash,
                'email': user.email,
                'paid_user': user.paid_user,
                'usage_count': user.usage_count,
                'premium_usage_count': user.premium_usage_count,
                'subscription_expires_at': user.subscription_expires_at
            }
        
        logger.info("User data loaded from database successfully")
        return users_dict
    except Exception as e:
        logger.error(f"Error loading user data from database: {e}")
        return {}
    finally:
        session.close()

# Chat history functions
def save_chat_history(username, chat_history):
    """Save user chat history to PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when saving chat history")
            return False
        
        # Check if chat history exists
        chat = session.query(ChatHistory).filter_by(user_id=user.id).first()
        
        if chat:
            # Update existing chat history
            chat.content = chat_history
        else:
            # Create new chat history
            new_chat = ChatHistory(
                user_id=user.id,
                content=chat_history
            )
            session.add(new_chat)
        
        session.commit()
        logger.info(f"Chat history for {username} saved to database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving chat history to database: {e}")
        return False
    finally:
        session.close()

def load_chat_history(username):
    """Load user chat history from PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when loading chat history")
            return []
        
        chat = session.query(ChatHistory).filter_by(user_id=user.id).first()
        
        if not chat:
            logger.info(f"No chat history found for {username}")
            return []
        
        logger.info(f"Chat history for {username} loaded from database successfully")
        return chat.content
    except Exception as e:
        logger.error(f"Error loading chat history from database: {e}")
        return []
    finally:
        session.close()

def delete_chat_history(username):
    """Delete user chat history from PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when deleting chat history")
            return False
        
        chat = session.query(ChatHistory).filter_by(user_id=user.id).first()
        
        if not chat:
            logger.warning(f"No chat history found for {username}")
            return False
        
        session.delete(chat)
        session.commit()
        logger.info(f"Chat history for {username} deleted from database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting chat history from database: {e}")
        return False
    finally:
        session.close()

# Forecast and model storage functions
def save_forecast(username, forecast_name, forecast_data):
    """Save forecast data to PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when saving forecast")
            return False
        
        # Check if forecast exists
        forecast = session.query(Forecast).filter_by(user_id=user.id, name=forecast_name).first()
        
        if forecast:
            # Update existing forecast
            forecast.data = forecast_data
        else:
            # Create new forecast
            new_forecast = Forecast(
                user_id=user.id,
                name=forecast_name,
                data=forecast_data
            )
            session.add(new_forecast)
        
        session.commit()
        logger.info(f"Forecast {forecast_name} saved to database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving forecast to database: {e}")
        return False
    finally:
        session.close()

def load_forecast(username, forecast_name):
    """Load forecast data from PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when loading forecast")
            return None
        
        forecast = session.query(Forecast).filter_by(user_id=user.id, name=forecast_name).first()
        
        if not forecast:
            logger.warning(f"Forecast {forecast_name} not found")
            return None
        
        logger.info(f"Forecast {forecast_name} loaded from database successfully")
        return forecast.data
    except Exception as e:
        logger.error(f"Error loading forecast from database: {e}")
        return None
    finally:
        session.close()

def save_model(username, model_name, model_binary):
    """Save model binary to PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when saving model")
            return False
        
        # Check if model exists
        model = session.query(Model).filter_by(user_id=user.id, name=model_name).first()
        
        if model:
            # Update existing model
            model.binary_data = model_binary
        else:
            # Create new model
            new_model = Model(
                user_id=user.id,
                name=model_name,
                binary_data=model_binary
            )
            session.add(new_model)
        
        session.commit()
        logger.info(f"Model {model_name} saved to database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving model to database: {e}")
        return False
    finally:
        session.close()

def load_model(username, model_name):
    """Load user's saved model from PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when loading model")
            return None
        
        model = session.query(Model).filter_by(user_id=user.id, name=model_name).first()
        
        if not model:
            logger.warning(f"Model {model_name} not found for user {username}")
            return None
        
        binary_data = model.binary_data
        
        try:
            loaded_model = pickle.loads(binary_data)
            logger.info(f"Model {model_name} for {username} loaded from database successfully")
            return loaded_model
        except Exception as e:
            logger.error(f"Error deserializing model: {e}")
            return None
    except Exception as e:
        logger.error(f"Error loading model from database: {e}")
        return None
    finally:
        session.close()

# Transaction functions
def save_transaction(name, email, phone, app_id, order_id):
    """Save transaction to PostgreSQL database"""
    session = Session()
    
    try:
        # Check if transaction exists
        transaction = session.query(Transaction).filter_by(app_id=app_id, order_id=order_id).first()
        
        if transaction:
            logger.warning(f"Transaction {app_id} {order_id} already exists")
            return False
        
        # Create new transaction
        new_transaction = Transaction(
            name=name,
            email=email,
            phone=phone,
            app_id=app_id,
            order_id=order_id
        )
        session.add(new_transaction)
        session.commit()
        
        logger.info(f"Transaction {app_id} {order_id} saved to database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving transaction to database: {e}")
        return False
    finally:
        session.close()

def get_transaction_by_id(app_id, order_id):
    """Get transaction by ID from PostgreSQL database"""
    session = Session()
    
    try:
        transaction = session.query(Transaction).filter_by(app_id=app_id, order_id=order_id).first()
        
        if not transaction:
            logger.warning(f"Transaction {app_id} {order_id} not found")
            return None
        
        transaction_dict = {
            'name': transaction.name,
            'email': transaction.email,
            'phone': transaction.phone,
            'app_id': transaction.app_id,
            'order_id': transaction.order_id
        }
        
        logger.info(f"Transaction {app_id} {order_id} retrieved from database successfully")
        return transaction_dict
    except Exception as e:
        logger.error(f"Error retrieving transaction from database: {e}")
        return None
    finally:
        session.close()

# Initialize database when this module is imported
try:
    initialize_database()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}") 
    
def test_connection():
    """Test the database connection and return connection status"""
    try:
        # Display environment variables for debugging
        print(f"Environment variables:")
        print(f"DB_USER: {os.getenv('DB_USER', 'Not set')}")
        print(f"DB_HOST: {os.getenv('DB_HOST', 'Not set')}")
        print(f"DB_PORT: {os.getenv('DB_PORT', 'Not set')}")
        print(f"DB_NAME: {os.getenv('DB_NAME', 'Not set')}")
        print(f"Connection URL: {DATABASE_URL.replace(DB_PASSWORD, '********')}")
        
        # Try to connect and run a simple query
        with engine.connect() as connection:
            # Simply establishing a connection is enough to verify it works
            print("Successfully established a database connection!")
            
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        print(f"\nError details: {str(e)}")
        print("\nTroubleshooting suggestions:")
        print("1. Check if PostgreSQL is running (brew services list)")
        print("2. Verify username and password in .env file")
        print("3. Make sure the database exists ('subscriptionpanel')")
        print("4. Check if the roles/users are correctly set up in PostgreSQL")
        print("5. Try connecting with: psql -U postgres -h localhost -p 5432 -d subscriptionpanel")
        return False

if __name__ == "__main__":
    # Run connection test if script is executed directly
    print("Running database connection test...")
    connection_result = test_connection()
    print(f"\nDatabase connection test result: {'Success' if connection_result else 'Failed'}") 

