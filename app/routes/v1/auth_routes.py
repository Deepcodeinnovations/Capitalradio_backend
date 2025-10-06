from fastapi import APIRouter
from app.apiv1.http.auth import AdminAuthController, UserAuthController

auth_routers = APIRouter()
auth_routers.include_router(AdminAuthController.router, prefix="/auth/admin", tags=["Admin Authentication"])
auth_routers.include_router(UserAuthController.router, prefix="/user/auth", tags=["User Authentication"])
