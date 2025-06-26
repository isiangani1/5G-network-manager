from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from app.db.models import User, UserInDB
from app.db.database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={401: {"description": "Unauthorized"}},
)


@router.post("/login", response_model=dict)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    OAuth2 compatible token login, get an access token for future requests.
    
    - **username**: Your username
    - **password**: Your password
    
    Returns:
        A dictionary containing the access token and token type
    """
    user = await User.get_user_async(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Refresh an access token.
    
    Requires a valid refresh token in the Authorization header.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserInDB)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user information.
    
    Requires authentication.
    """
    return current_user
