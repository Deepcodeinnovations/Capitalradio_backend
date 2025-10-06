from fastapi import APIRouter, Request, status, HTTPException, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from app.utils.pagination import paginate_data
from app.utils.helper_functions import convert_status_to_boolean
from fastapi.encoders import jsonable_encoder
from app.utils.security import get_current_user_details
from app.apiv1.services.admin.AdminAuthService import (
    authenticate_admin,
    create_admin,
    update_admin,
    delete_admin,
    send_admin_password_reset,
    verify_admin_reset_code,
    update_admin_password,
    change_admin_password,
    logout_admin,
    get_admin_list,
    get_admin_by_id
)
from typing import Optional
import json

router = APIRouter()


@router.post("/login", status_code=status.HTTP_200_OK)
async def admin_login(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        remember = convert_status_to_boolean(form_data.get("remember", False))
        device_fingerprint = form_data.get("device_fingerprint")
        
        if not email or not password:
            return returnsdata.error_msg("Email and password are required", ERROR)
            
        auth_data = await authenticate_admin(db, email, password, remember, device_fingerprint)
        return returnsdata.success(data=auth_data, msg="Admin login successful", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def admin_logout(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        device_fingerprint = form_data.get("device_fingerprint")
        success = await logout_admin(db, current_user.get("id"), device_fingerprint)
        return returnsdata.success_msg(msg="Admin logout successful", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_new_admin(
    request: Request, 
    db: AsyncSession = Depends(get_database), 
    current_user = Depends(get_current_user_details),
    image: Optional[UploadFile] = File(None)
):
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        # Handle image upload
        if image and image.filename:
            data["image"] = image
            
        # Convert boolean fields
        if "status" in data:
            data["status"] = convert_status_to_boolean(data["status"])
        if "allow_login" in data:
            data["allow_login"] = convert_status_to_boolean(data["allow_login"])
        
        admin = await create_admin(db, data, current_user.get("id"))
        return returnsdata.success(data=admin, msg="Admin created successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users", status_code=status.HTTP_200_OK)
async def get_all_admins(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        search = form_data.get("search")
        role_filter = form_data.get("role")
        status_filter = form_data.get("status")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 10))
        include_total = convert_status_to_boolean(form_data.get("include_total", False))
        
        result = await get_admin_list(
            db, 
            current_user.get("id"), 
            page, 
            per_page, 
            search, 
            role_filter,
            status_filter,
            include_total
        )
        return returnsdata.success(data=result, msg="Users retrieved successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/{id}", status_code=status.HTTP_200_OK)
async def get_admin_details(id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        admin = await get_admin_by_id(db, id, current_user.get("id"))
        return returnsdata.success(data=admin, msg="User details retrieved successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/update/{id}", status_code=status.HTTP_200_OK)
async def update_admin_details(
    id: str, 
    request: Request, 
    db: AsyncSession = Depends(get_database), 
    current_user = Depends(get_current_user_details),
    image: Optional[UploadFile] = File(None)
):
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        # Handle image upload
        if image and image.filename:
            data["image"] = image
        
        # Convert boolean fields
        if "status" in data:
            data["status"] = convert_status_to_boolean(data["status"])
        if "allow_login" in data:
            data["allow_login"] = convert_status_to_boolean(data["allow_login"])
        
        admin = await update_admin(db, id, data, current_user.get("id"))
        return returnsdata.success(data=admin, msg="User updated successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/delete/{id}", status_code=status.HTTP_200_OK)
async def delete_admin_endpoint(id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        hard_delete = convert_status_to_boolean(form_data.get("hard_delete", False))
        success = await delete_admin(db, id, current_user.get("id"), hard_delete)
        delete_type = "permanently deleted" if hard_delete else "deactivated"
        return returnsdata.success_msg(msg=f"User {delete_type} successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


# Password Reset Routes
@router.post("/password_reset", status_code=status.HTTP_200_OK)
async def forgot_admin_password(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        email = form_data.get("email")
        if not email:
            return returnsdata.error_msg("Email is required", ERROR)
        result = await send_admin_password_reset(db, email)
        return returnsdata.success_msg(msg="Password reset code sent to your email", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/verify_reset", status_code=status.HTTP_200_OK)
async def verify_password_reset_code(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        code = form_data.get("code")
        email = form_data.get("email")
        
        if not code:
            return returnsdata.error_msg("Verification code is required", ERROR)
            
        admin = await verify_admin_reset_code(db, code, email)
        return returnsdata.success(
            data={"admin_id": admin.id, "email": admin.email}, 
            msg="Verification code is valid", 
            status=SUCCESS
        )
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/update_password", status_code=status.HTTP_200_OK)
async def reset_admin_password(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        user_id = form_data.get("admin_id")
        
        if not all([email, password, user_id]):
            return returnsdata.error_msg("Email, password, and user_id are required", ERROR)
            
        await update_admin_password(db, email, password, user_id)
        return returnsdata.success_msg(msg="Password updated successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/password/change", status_code=status.HTTP_200_OK)
async def change_password(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        current_password = form_data.get("current_password")
        new_password = form_data.get("new_password")
        
        if not all([current_password, new_password]):
            return returnsdata.error_msg("Current password and new password are required", ERROR)
            
        success = await change_admin_password(db, current_user.get("id"), current_password, new_password)
        return returnsdata.success_msg(msg="Password changed successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


# Profile Routes
@router.post("/authuser", status_code=status.HTTP_200_OK)
async def get_auth_user(db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        admin = await get_admin_by_id(db, current_user.get("id"), current_user.get("id"))
        return returnsdata.success(data=admin, msg="Profile retrieved successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/profile/me", status_code=status.HTTP_200_OK)
async def get_my_profile(db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        admin = await get_admin_by_id(db, current_user.get("id"), current_user.get("id"))
        return returnsdata.success(data=admin, msg="Profile retrieved successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)


@router.post("/users/profile/update", status_code=status.HTTP_200_OK)
async def update_my_profile(
    request: Request, 
    db: AsyncSession = Depends(get_database), 
    current_user = Depends(get_current_user_details),
    image: Optional[UploadFile] = File(None)
):
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        # Handle image upload
        if image and image.filename:
            data["image"] = image
        
        # Convert boolean fields
        if "status" in data:
            data["status"] = convert_status_to_boolean(data["status"])
        if "allow_login" in data:
            data["allow_login"] = convert_status_to_boolean(data["allow_login"])
        
        admin = await update_admin(db, current_user.get("id"), data, current_user.get("id"))
        return returnsdata.success(data=admin, msg="Profile updated successfully", status=SUCCESS)
    except HTTPException as e:
        return returnsdata.error_msg(e.detail, ERROR)