from fastapi import APIRouter
from app.apiv1.http.user import UserGlobalAccessController
from app.apiv1.http.user import StreamingController

user_routers = APIRouter()
user_routers.include_router(UserGlobalAccessController.router, prefix="/user", tags=["User Global Access"])
user_routers.include_router(StreamingController.router, prefix="/user/streaming", tags=["User Streaming Access"])
