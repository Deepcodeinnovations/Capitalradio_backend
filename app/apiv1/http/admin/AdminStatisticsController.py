from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from app.utils.security import get_current_user_details, verify_admin_access
from app.apiv1.services.admin.AdminStatisticsService import get_dashboard_analytics
from typing import Dict, Any

router = APIRouter()

@router.post("/analytics", status_code=status.HTTP_200_OK)
async def get_dashboard_analytics_endpoint(db: AsyncSession = Depends(get_database),current_user: Dict[str, Any] = Depends(get_current_user_details)):
    try:
        analytics_data = await get_dashboard_analytics(db)
        
        return returnsdata.success(data=analytics_data, msg="Dashboard analytics retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get dashboard analytics: {str(e)}", ERROR)
