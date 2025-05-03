import os
import json
import pickle
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get PostgreSQL connection details from environment variables
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres2')

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
            # Check if user exists
            user = session.query(User).filter_by(username=username).first()            
            if user:
                # Update existing user
                user.password_hash = user_data.get('password', '')
                user.email = user_data.get('email', '')
                user.paid_user = user_data.get('paid_user', 0)
                user.usage_count = user_data.get('usage_count', 0)
            else:
                # Create new user
                new_user = User(
                    username=username,
                    password_hash=user_data.get('password', ''),
                    email=user_data.get('email', ''),
                    paid_user=user_data.get('paid_user', 0),
                    usage_count=user_data.get('usage_count', 0)
                )
                session.add(new_user)
        
        session.commit()
        logger.info("User data saved to database successfully")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving user data to database: {e}")
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
                'usage_count': user.usage_count
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
    """Load model binary from PostgreSQL database"""
    session = Session()
    
    try:
        user = session.query(User).filter_by(username=username).first()
        
        if not user:
            logger.warning(f"User {username} not found when loading model")
            return None
        
        model = session.query(Model).filter_by(user_id=user.id, name=model_name).first()
        
        if not model:
            logger.warning(f"Model {model_name} not found")
            return None
        
        logger.info(f"Model {model_name} loaded from database successfully")
        return model.binary_data
    except Exception as e:
        logger.error(f"Error loading model from database: {e}")
        return None
    finally:
        session.close()

# Initialize database when this module is imported
try:
    initialize_database()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}") 