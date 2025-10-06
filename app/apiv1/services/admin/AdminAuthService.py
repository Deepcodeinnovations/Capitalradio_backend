from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from slugify import slugify
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.database import get_database
from app.utils.helper_functions import log_system_error, convert_status_to_boolean
from app.models.UserModel import User
from app.utils.messaging_service import MessagingService
from app.apiv1.email_templates.get_password_reset_template import get_password_reset_template
from app.utils.security import verify_password, create_user_access_token, invalidate_user_tokens, is_valid_email, get_password_hash
import re
import random


def validate_admin_password(password: str) -> tuple[bool, str]:
    """Validate admin password requirements: 8+ chars, uppercase, lowercase, number, special char"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"


async def authenticate_admin(db: AsyncSession, email: str, password: str, remember: bool = False, device_fingerprint: Optional[str] = None) -> Dict[str, Any]:
    try:
        result = await db.execute(
            select(User).where(
                User.email == email, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = result.scalar_one_or_none()
 
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

        if not verify_password(password, admin.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

        if not admin.status:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account is deactivated")

        if not admin.allow_login:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login not allowed for this account")

        expires_delta = timedelta(days=30) if remember else None
        device_fp = device_fingerprint or f"admin-{admin.id}"
        admin_data = await admin.to_dict()
        token_data = await create_user_access_token(
            db=db, 
            user=admin_data, 
            data={"device_fingerprint": device_fp}, 
            expires_delta=expires_delta
        )
        
        # Update last seen
        admin.last_seen = datetime.utcnow()
        await db.commit()
        
        return {
            "admin": await admin.to_dict_with_relations(db=db), 
            "authtoken": token_data
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def create_admin(db: AsyncSession, data: Dict[str, Any], creator_id: str) -> Dict[str, Any]:
    try:
        # Verify creator has admin role
        creator_result = await db.execute(
            select(User).where(
                User.id == creator_id, 
                User.role == 'admin',
                User.state == True
            )
        )
        creator = creator_result.scalar_one_or_none()
        if not creator:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create admin accounts")

        email = data.get("email")
        password = data.get("password")
        name = data.get("name")
        role = data.get("role", "editor")
        image = data.get("image")

        # Validate required fields
        if not all([email, password, name]):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email, password, and name are required")

        if not is_valid_email(email):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")

        # Validate role
        if role not in ['admin', 'editor', 'presenter']:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role must be admin, editor, or presenter")

        # Validate password
        is_valid, message = validate_admin_password(password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

        # Check if user already exists
        existing_user = await db.execute(
            select(User).where(User.email == email, User.state == True)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

        # Generate unique slug
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while True:
            slug_check = await db.execute(select(User).where(User.slug == slug, User.state == True))
            if not slug_check.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Handle image upload
        image_path = None
        image_url = None
        if image:
            from app.utils.file_upload import save_upload_file
            image_path, image_url = await save_upload_file(image, "admin/profile")

        # Hash password
        password_hash = get_password_hash(password)
        
        # Create new admin user
        new_admin = User(
            name=name,
            email=email,
            password=password_hash,
            slug=slug,
            role=role,
            phone=data.get("phone"),
            address=data.get("address"),
            about=data.get("about"),
            image_path=image_path,
            image_url=image_url,
            email_verified_at=datetime.utcnow(),
            status=convert_status_to_boolean(data.get("status", True)),
            allow_login=convert_status_to_boolean(data.get("allow_login", True)),
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)
        return await new_admin.to_dict_with_relations(db=db)
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="create_admin")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def update_admin(db: AsyncSession, admin_id: str, data: Dict[str, Any], updater_id: str) -> Dict[str, Any]:
    try:
        # Verify updater has admin role or is updating themselves
        updater_result = await db.execute(
            select(User).where(
                User.id == updater_id,
                User.state == True
            )
        )
        updater = updater_result.scalar_one_or_none()
        
        # Check permissions
        if not updater:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")
        
        is_admin = updater.role == 'admin'
        is_self_update = updater_id == admin_id
        
        if not is_admin and not is_self_update:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        # Get admin to update
        admin_result = await db.execute(
            select(User).where(
                User.id == admin_id, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        # Update name and regenerate slug if needed
        if "name" in data and data["name"]:
            admin.name = data["name"]
            # Update slug if name changed
            base_slug = slugify(data["name"])
            slug = base_slug
            counter = 1
            while True:
                slug_check = await db.execute(
                    select(User).where(User.slug == slug, User.id != admin_id, User.state == True)
                )
                if not slug_check.scalar_one_or_none():
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1
            admin.slug = slug

        # Update email
        if "email" in data and data["email"]:
            if not is_valid_email(data["email"]):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
            existing_user = await db.execute(
                select(User).where(User.email == data["email"], User.id != admin_id, User.state == True)
            )
            if existing_user.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
            admin.email = data["email"]

        # Handle image upload
        if "image" in data and data["image"]:
            from app.utils.file_upload import save_upload_file, remove_file
            if admin.image_path:
                remove_file(admin.image_path)
            image_path, image_url = await save_upload_file(data["image"], "admin/profile")
            admin.image_url = image_url
            admin.image_path = image_path

        # Update basic fields
        if "phone" in data:
            admin.phone = data["phone"]
        if "address" in data:
            admin.address = data["address"]
        if "about" in data:
            admin.about = data["about"]

        # Only admins can change role, status, and allow_login
        if is_admin:
            if "role" in data and data["role"] in ['admin', 'editor', 'presenter']:
                admin.role = data["role"]
            if "status" in data:
                admin.status = convert_status_to_boolean(data["status"])
            if "allow_login" in data:
                admin.allow_login = convert_status_to_boolean(data["allow_login"])

        admin.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(admin)
        return await admin.to_dict_with_relations(db=db)
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="update_admin")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def delete_admin(db: AsyncSession, admin_id: str, deleter_id: str, hard_delete: bool = False) -> bool:
    try:
        # Verify deleter has admin role
        deleter_result = await db.execute(
            select(User).where(
                User.id == deleter_id, 
                User.role == 'admin',
                User.state == True
            )
        )
        deleter = deleter_result.scalar_one_or_none()
        if not deleter:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete admin accounts")

        # Prevent self-deletion
        if admin_id == deleter_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot delete your own account")

        admin_result = await db.execute(
            select(User).where(
                User.id == admin_id, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        # Check if this is the last admin
        admin_count_result = await db.execute(
            select(func.count(User.id)).where(User.role == 'admin', User.state == True)
        )
        admin_count = admin_count_result.scalar()
        if admin.role == 'admin' and admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot delete the last admin account")

        if hard_delete:
            # Hard delete - remove from database
            await admin.delete_with_relations(db=db)
        else:
            # Soft delete - set state to False
            admin.state = False
            admin.status = False
            admin.updated_at = datetime.utcnow()
            await db.commit()

        return True
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="delete_admin")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def send_admin_password_reset(db: AsyncSession, email: str):
    messaging_service = MessagingService()
    try:
        if not is_valid_email(email):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")

        result = await db.execute(
            select(User).where(
                User.email == email, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found")

        code = str(random.randint(100000, 999999))
        subject = "Reset your Admin Password"
        html_content = get_password_reset_template(code)
    
        result = await messaging_service.send_email(
            recipient_email=email, 
            subject=subject, 
            html_content=html_content
        )
        if result["status"] == "error":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(result["message"]))

        admin.verify_code = code
        admin.verify_code_at = datetime.utcnow()
        await db.commit()
        await db.refresh(admin)
        return True
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="send_admin_password_reset")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def verify_admin_reset_code(db: AsyncSession, code: str, email: Optional[str] = None):
    try:
        query = select(User).where(
            User.verify_code == code, 
            User.role.in_(['admin', 'editor', 'presenter']),
            User.state == True
        )
        if email:
            query = query.where(User.email == email)
            
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code")

        # Check if code is expired (1 hour)
        if not admin.verify_code_at or (datetime.utcnow() - admin.verify_code_at).total_seconds() > 3600:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Verification code has expired")

        admin.verify_code = None
        admin.verify_code_at = None
        await db.commit()
        await db.refresh(admin)
        return admin
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="verify_admin_reset_code")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def update_admin_password(db: AsyncSession, email: str, password: str, user_id: str):
    try:
        result = await db.execute(
            select(User).where(
                User.email == email, 
                User.id == user_id, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please reload page and repeat this process")

        # Validate new password
        is_valid, message = validate_admin_password(password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

        hashed_password = get_password_hash(password)
        admin.password = hashed_password
        admin.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(admin)
        return admin
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="update_admin_password")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def change_admin_password(db: AsyncSession, admin_id: str, current_password: str, new_password: str):
    try:
        result = await db.execute(
            select(User).where(
                User.id == admin_id, 
                User.role.in_(['admin', 'editor', 'presenter']),
                User.state == True
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        # Verify current password
        if not verify_password(current_password, admin.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

        # Validate new password
        is_valid, message = validate_admin_password(new_password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

        # Check if new password is different from current
        if verify_password(new_password, admin.password):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different from current password")

        hashed_password = get_password_hash(new_password)
        admin.password = hashed_password
        admin.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(admin)
        return True
    except Exception as e:
        await db.rollback()
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="change_admin_password")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def logout_admin(db: AsyncSession, admin_id: str, device_fingerprint: Optional[str] = None):
    try:
        device_fp = device_fingerprint or f"admin-{admin_id}"
        await invalidate_user_tokens(admin_id, device_fp, db)
        return True
    except Exception as e:
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="logout_admin")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to logout: {str(e)}")


async def get_admin_list(
    db: AsyncSession, 
    admin_id: str, 
    page: int = 1, 
    per_page: int = 10, 
    search: Optional[str] = None, 
    role_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    include_total: bool = False
) -> Dict[str, Any]:
    try:
        # Verify requester has admin role
        requester_result = await db.execute(
            select(User.id).where(
                User.id == admin_id, 
                User.role == 'admin', 
                User.state == True
            )
        )
        if not requester_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view admin list")
        
        # Calculate metrics if requested
        metrics = None
        if include_total:
            total_users_result = await db.execute(
                select(func.count(User.id)).where(User.state == True)
            )
            total_users = total_users_result.scalar() or 0
            
            admin_count_result = await db.execute(
                select(func.count(User.id)).where(User.role == 'admin', User.state == True)
            )
            admin_count = admin_count_result.scalar() or 0
            
            editor_count_result = await db.execute(
                select(func.count(User.id)).where(User.role == 'editor', User.state == True)
            )
            editor_count = editor_count_result.scalar() or 0
            
            presenter_count_result = await db.execute(
                select(func.count(User.id)).where(User.role == 'presenter', User.state == True)
            )
            presenter_count = presenter_count_result.scalar() or 0
            
            active_users_result = await db.execute(
                select(func.count(User.id)).where(User.status == True, User.state == True)
            )
            active_users = active_users_result.scalar() or 0
            
            inactive_users_result = await db.execute(
                select(func.count(User.id)).where(User.status == False, User.state == True)
            )
            inactive_users = inactive_users_result.scalar() or 0
            
            metrics = {
                "total_users": total_users,
                "users_by_role": {
                    "admin": admin_count,
                    "editor": editor_count,
                    "presenter": presenter_count
                },
                "active_users": active_users,
                "inactive_users": inactive_users
            }
        
        # Build base query with filters
        query = select(User).where(
            User.role.in_(['admin', 'editor', 'presenter']), 
            User.state == True
        )
        
        # Apply filters
        if search:
            search_filter = or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.about.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            
        if role_filter and role_filter in ['admin', 'editor', 'presenter']:
            query = query.where(User.role == role_filter)
            
        if status_filter:
            status_bool = convert_status_to_boolean(status_filter)
            query = query.where(User.status == status_bool)
            
        query = query.order_by(User.created_at.desc())
        
        # Calculate pagination
        total_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar() or 0
        
        offset = (page - 1) * per_page
        paginated_query = query.offset(offset).limit(per_page)
        
        result = await db.execute(paginated_query)
        users = result.scalars().all()
        
        # Transform users
        user_list = []
        for user in users:
            user_dict = await user.to_dict_with_relations(db)
            user_list.append(user_dict)
        
        # Build pagination response
        has_next = (page * per_page) < total
        has_prev = page > 1
        
        response = {
            "data": user_list,
            "current_page": page,
            "per_page": per_page,
            "total": total,
            "last_page": (total + per_page - 1) // per_page,
            "from": offset + 1 if user_list else 0,
            "to": offset + len(user_list),
            "has_next": has_next,
            "has_prev": has_prev
        }
        
        if metrics:
            response["metrics"] = metrics
            
        return response
        
    except Exception as e:
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="get_admin_list")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_admin_by_id(db: AsyncSession, admin_id: str, requester_id: str) -> Dict[str, Any]:
    try:
        # Verify requester has admin role or is requesting their own data
        requester_result = await db.execute(
            select(User).where(
                User.id == requester_id, 
                User.state == True
            )
        )
        requester = requester_result.scalar_one_or_none()
        
        if not requester:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")
            
        # Check if requester is admin or requesting own data
        is_admin = requester.role == 'admin'
        is_self_request = requester_id == admin_id
        
        if not is_admin and not is_self_request:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        admin_result = await db.execute(
            select(User).where(
                User.id == admin_id, 
                User.role.in_(['admin', 'editor', 'presenter']), 
                User.state == True
            )
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        return await admin.to_dict_with_relations(db=db)
    except Exception as e:
        if "log_system_error" in globals():
            await log_system_error(db=db, service="AdminAuthService", error=e, access_function="get_admin_by_id")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))