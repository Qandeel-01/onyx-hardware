"""Authentication module with JWT token handling."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


class TokenRequest(BaseModel):
    """Token request model."""
    user_id: int
    email: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token.
    
    Args:
        data: Dictionary of claims to encode
        expires_delta: Optional expiration time offset
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)) -> dict:
    """Verify JWT token and return user info.
    
    Args:
        credentials: HTTP Bearer credentials from request
        
    Returns:
        Dictionary with user_id and email
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError as e:
        logger.warning(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    return {"user_id": user_id, "email": email}


@router.post("/login", response_model=TokenResponse)
async def login(request: TokenRequest):
    """Generate access token for user.
    
    Args:
        request: User credentials (user_id and email)
        
    Returns:
        JWT access token
    """
    logger.info(f"Login request for user {request.user_id}")
    
    token = create_access_token(
        data={"sub": request.user_id, "email": request.email}
    )
    return TokenResponse(access_token=token)


@router.post("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify current token validity.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User info if token is valid
    """
    return {"valid": True, "user": current_user}
