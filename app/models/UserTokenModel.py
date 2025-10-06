from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from app.models.BaseModel import Base
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import uuid

# Constants for field lengths
MAX_TOKEN_LENGTH = 255
MAX_DEVICE_INFO_LENGTH = 500
MAX_USER_AGENT_LENGTH = 255
MAX_FINGERPRINT_LENGTH = 100

class Usertoken(Base):
    __tablename__ = "user_tokens"
    
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    access_token = Column(String(600), nullable=False, index=True)
    refresh_token = Column(String(255), nullable=True)
    token_type = Column(String(20), nullable=False, default="bearer")
    expires_at = Column(DateTime, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 addresses can be long
    expired_at = Column(DateTime, nullable=True)
    user_agent = Column(String(255), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    device_fingerprint = Column(String(100), nullable=True)

    user = relationship("User", backref=backref("tokens", lazy="selectin"))
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'device_info': self.device_info,
            'ip_address': self.ip_address,
            'expired_at': self.expired_at.isoformat() if self.expired_at else None,
            'user_agent': self.user_agent,
            'revoked': self.revoked,
            'device_fingerprint': self.device_fingerprint,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            # Reload the model with any related entities
            await db.refresh(self, ['user'])   
            data = await self.to_dict()
            # Add related entities data
            if self.user:
                data['user'] = await self.user.to_dict()
                
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert user token to dictionary with relations: {str(e)}")