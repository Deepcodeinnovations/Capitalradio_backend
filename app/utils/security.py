from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Annotated
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from passlib.context import CryptContext
from app.database import get_database
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from app.models.UserModel import User
from app.models.UserTokenModel import Usertoken
import os
import re
import json
import logging
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoyOCwidXNlcm5hbWUiOiJyYW5kb21fdXNlciJ9.KfpKPkcoVZBIlVXZJ6eSpxFG6wlGbGUDnU8VlESnL-Q")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "6000000"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def create_user_access_token(db: AsyncSession,user: Dict[str, Any],data: Dict[str, Any],expires_delta: Optional[timedelta] = None) -> Dict[str, Any]:
   try:
       if not isinstance(user, dict) or not user.get('id') or not user.get('email'):
           raise ValueError("Invalid user data: missing required fields")
       expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

       token_data = {
           "sub": str(user["id"]),
           "email": str(user["email"]),
           "exp": expire,
           "device_fingerprint": str(data.get("device_fingerprint", ""))
       }
       encoded_jwt = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

       if token_data["device_fingerprint"]:
           try:
               # Invalidate all existing tokens for this device first
               invalidate_stmt = select(Usertoken).where(and_(Usertoken.user_id == user["id"], Usertoken.device_fingerprint == token_data["device_fingerprint"]))
               result = await db.execute(invalidate_stmt)
               existing_tokens = result.scalars().all()
               
               for token in existing_tokens:
                   token.revoked = True
                   token.status = False
                   db.add(token)

               # Create new token
               new_token = Usertoken(
                   user_id=user["id"],
                   access_token=encoded_jwt,
                   token_type="bearer",
                   expires_at=expire,
                   device_fingerprint=token_data["device_fingerprint"],
                   last_used_at=datetime.now(timezone.utc)
               )
               db.add(new_token)
               await db.commit()

           except SQLAlchemyError as e:
               await db.rollback()
               raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")

       return {
           "access_token": encoded_jwt,
           "token_type": "bearer",
           "expires_at": expire.isoformat(),
           "device_fingerprint": token_data["device_fingerprint"]
       }
   except ValueError as e:
       raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
   except Exception as e:
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create access token")

async def extract_token_from_header(authorization: Annotated[str | None, Header()] = None) -> str:
   if not authorization:
       raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")
   try:
       scheme, token = authorization.split()
       if scheme.lower() != "bearer":
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
       return token
   except ValueError:
       raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization format")

async def decode_and_validate_token(token: str, db: AsyncSession) -> Dict[str, Any]:
   try:
       payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
       user_id = payload.get("sub")
       if not user_id:
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
       
       token_query = select(Usertoken).where(
           Usertoken.user_id == user_id,
           Usertoken.access_token == token,
           Usertoken.revoked == False,
           Usertoken.expires_at > datetime.now(timezone.utc),
           Usertoken.status == True,
           Usertoken.state == True
       ).order_by(Usertoken.created_at.desc()).limit(1)

       result = await db.execute(token_query)
       token_data = result.scalar_one_or_none()
       
       if not token_data:
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token not found or expired")

       token_data.last_used_at = datetime.now(timezone.utc)
       await db.commit()
       return payload
       
   except JWTError:
       raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
   except Exception as e:
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error validating token: {str(e)}")

async def get_user_from_token(payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
   try:
       user_id = payload.get("sub")
       stmt = select(User).where(and_(User.id == user_id, User.status == True))
       result = await db.execute(stmt)
       user = result.scalar_one_or_none()
       
       if not user:
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="User not found or inactive")
       user.last_seen = datetime.now(timezone.utc)
       await db.commit()
       user_data = await user.to_dict()
       print("===============================user data=======================================================================")
       print(user_data)
       return user_data
   except HTTPException:
       raise
   except Exception as e:
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Something Wrong Has Happened: {str(e)}")

async def get_current_user_details(authorization: Optional[str] = Header(None),db: AsyncSession = Depends(get_database)) -> Dict[str, Any]:
   token = await extract_token_from_header(authorization)
   print("======================================================================================================")
   print(token)
   payload = await decode_and_validate_token(token, db)
   print("======================================================================================================")
   print(payload)
   user_data = await get_user_from_token(payload, db)
   print("======================================================================================================")
   print(user_data)
   return user_data


async def invalidate_user_tokens(user_id: str,device_fingerprint: str,db: AsyncSession) -> None:
   try:
       query = select(Usertoken).where(and_(Usertoken.user_id == user_id, Usertoken.device_fingerprint == device_fingerprint))
       result = await db.execute(query)
       token_records = result.scalars().all()

       if token_records:
           for token_record in token_records:
               token_record.revoked = True
               token_record.status = False
               db.add(token_record)
           await db.commit()
   except Exception as e:
       await db.rollback()
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to invalidate tokens")

def verify_admin_access(current_user: Dict[str, Any]) -> None:
   try:
       if not current_user:
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
       authuser = None
       if hasattr(current_user, 'status_code'):
          import json
          authuser = json.loads(current_user.body.decode())
       else:
           authuser = current_user
       if authuser.get('role') != 'admin':
           raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
       return authuser
   except Exception as e:
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Access verification error: {str(e)}")

def verify_password(plain_password: str, hashed_password: str) -> bool:
   return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
   return pwd_context.hash(password)

def is_valid_email(email: str) -> bool:
   email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
   return re.match(email_regex, email) is not None