"""
JWT authentication router for Project ONYX.
Handles user authentication, token generation, and verification.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from jose import JWTError, jwt
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

# These will be imported from config in actual implementation
# Adjust according to your app.config.settings setup
try:
    from app.config import settings
except ImportError:
    # Fallback for testing
    class Settings:
        secret_key: str = "your-secret-key-change-in-production"
        algorithm: str = "HS256"
        access_token_expire_minutes: int = 30
    
    settings = Settings()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token (typically contains user_id as 'sub')
        expires_delta: Custom expiration time. If None, uses settings.access_token_expire_minutes
        
    Returns:
        Encoded JWT token as string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create access token"
        )


async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify JWT token and extract current user information.
    
    Args:
        credentials: HTTP Bearer credentials from request header
        
    Returns:
        Dictionary containing user_id and other decoded token data
        
    Raises:
        HTTPException: 401 if token is invalid, expired, or malformed
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        user_id: Optional[int] = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "user_id": user_id,
            "token": token,
            "exp": payload.get("exp")
        }
    
    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(current_user: Dict[str, Any] = Depends(get_current_user)) -> int:
    """
    Extract and return only the user_id from current user.
    
    Convenience dependency for endpoints that only need user_id.
    
    Args:
        current_user: Current authenticated user from get_current_user
        
    Returns:
        User ID as integer
    """
    return current_user["user_id"]


def verify_token_expiration(token: str) -> bool:
    """
    Check if a token is expired without raising exception.
    
    Args:
        token: JWT token to verify
        
    Returns:
        True if token is valid and not expired, False otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        exp = payload.get("exp")
        if exp is None:
            return False
        return datetime.utcfromtimestamp(exp) > datetime.utcnow()
    except JWTError:
        return False
