from fastapi import APIRouter
from app.routes.v1.auth_routes import auth_routers
from app.routes.v1.admin_routes import admin_routers
from app.routes.v1.user_routes import user_routers
from app.routes.v1.websockets_routes import websockets_routes

api_router = APIRouter()

api_router.include_router(auth_routers)
api_router.include_router(admin_routers)
api_router.include_router(user_routers)
api_router.include_router(websockets_routes)
