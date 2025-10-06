from sqlalchemy import Column, String, Text, DateTime, Integer
from app.models.base_model import Base
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import traceback

class SystemErrorLog(Base):
    __tablename__ = "system_error_logs"
    
    # Error Information
    service = Column(String(255), nullable=False)  # Service where error occurred
    access_function = Column(String(255), nullable=False)  # Function/endpoint that errored
    error_message = Column(Text, nullable=False)  # The error message
    error_type = Column(String(255), nullable=True)  # Type of error (e.g., ValueError, HTTPException)
    error_code = Column(String(50), nullable=True)  # HTTP status code or custom error code
    
    # Trace Information
    stack_trace = Column(Text, nullable=True)  # Full stack trace
    line_number = Column(Integer, nullable=True)  # Line where error occurred
    file_path = Column(String(500), nullable=True)  # File where error occurred
    
    # Request Context (optional)
    request_path = Column(String(500), nullable=True)  # API endpoint path
    request_method = Column(String(10), nullable=True)  # GET, POST, etc.
    request_data = Column(Text, nullable=True)  # Request body/params (be careful with sensitive data)
    
    # User Context (optional)
    user_id = Column(String(36), nullable=True)  # User who triggered the error
    user_ip = Column(String(45), nullable=True)  # User's IP address
    user_agent = Column(Text, nullable=True)  # User's browser/client info
    
    # Error Context
    severity = Column(String(20), default="ERROR")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    environment = Column(String(50), nullable=True)  # development, staging, production
    resolved = Column(String(3), default="no")  # yes, no
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(36), nullable=True)  # User ID who resolved
    notes = Column(Text, nullable=True)  # Additional notes about the error
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'service': self.service,
            'access_function': self.access_function,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'error_code': self.error_code,
            'stack_trace': self.stack_trace,
            'line_number': self.line_number,
            'file_path': self.file_path,
            'request_path': self.request_path,
            'request_method': self.request_method,
            'request_data': self.request_data,
            'user_id': self.user_id,
            'user_ip': self.user_ip,
            'user_agent': self.user_agent,
            'severity': self.severity,
            'environment': self.environment,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


