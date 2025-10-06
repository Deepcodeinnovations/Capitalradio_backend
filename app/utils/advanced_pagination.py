from typing import Optional, List, TypeVar, Generic, Any, Dict, Callable
from pydantic import BaseModel
from math import ceil
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy import func, or_
from app.utils.constants import BASE_URL

T = TypeVar('T')

class PaginationResponse(BaseModel, Generic[T]):
    data: Dict[str, Any]
    msg: str
    status: str
    status_code: int

async def paginate_query(db: AsyncSession, query: Select, page: int = 1, per_page: int = 50, path: str = "", transform_func: Optional[Callable] = None, include_total: bool = True, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page, per_page = max(1, page), max(1, min(per_page, 100))
    offset = (page - 1) * per_page
    
    total = 0
    if include_total:
        total_result = await db.execute(query.with_only_columns(func.count()).order_by(None))
        total = total_result.scalar() or 0
    
    result = await db.execute(query.offset(offset).limit(per_page + 1))
    items = result.scalars().all()
    has_next = len(items) > per_page
    if has_next: items = items[:-1]
    
    if transform_func:
        items = [await transform_func(item, db) for item in items]
    
    has_prev = page > 1
    if include_total:
        last_page, from_item, to_item = max(1, ceil(total / per_page)), offset + 1 if items else 0, offset + len(items)
    else:
        last_page, from_item, to_item, total = page + 1 if has_next else page, offset + 1 if items else 0, offset + len(items), None
    
    base_path = BASE_URL + path
    prev_url = f"{base_path}?page={page-1}&per_page={per_page}" if has_prev else None
    next_url = f"{base_path}?page={page+1}&per_page={per_page}" if has_next else None
    
    response_data = {
        "current_page": page,
        "data": items,
        "first_page_url": f"{base_path}?page=1&per_page={per_page}",
        "from": from_item,
        "last_page": last_page,
        "last_page_url": f"{base_path}?page={last_page}&per_page={per_page}" if include_total else None,
        "links": [
            {"url": prev_url, "label": "« Previous", "active": False},
            {"url": f"{base_path}?page={page}&per_page={per_page}", "label": str(page), "active": True},
            {"url": next_url, "label": "Next »", "active": False}
        ],
        "next_page_url": next_url,
        "path": base_path,
        "per_page": per_page,
        "prev_page_url": prev_url,
        "to": to_item,
        "has_next": has_next,
        "has_prev": has_prev
    }
    
    if metrics is not None:
        response_data["metrics"] = metrics
    
    if include_total: 
        response_data["total"] = total
    
    return response_data

def paginate_data(items: List[Any], total_count: int, page: Optional[int] = 1, per_page: Optional[int] = 50, path: str = "", metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page, per_page = max(1, page or 1), max(1, min(per_page or 50, 100))
    total_pages, offset = max(1, ceil(total_count / per_page)), (page - 1) * per_page
    page = min(page, total_pages)
    
    base_path = path or BASE_URL
    prev_url = f"{base_path}?page={page-1}&per_page={per_page}" if page > 1 else None
    next_url = f"{base_path}?page={page+1}&per_page={per_page}" if page < total_pages else None
    
    response_data = {
        "current_page": page,
        "data": items,
        "first_page_url": f"{base_path}?page=1&per_page={per_page}",
        "from": offset + 1 if items else 0,
        "last_page": total_pages,
        "last_page_url": f"{base_path}?page={total_pages}&per_page={per_page}",
        "links": [
            {"url": prev_url, "label": "« Previous", "active": False},
            {"url": f"{base_path}?page={page}&per_page={per_page}", "label": str(page), "active": True},
            {"url": next_url, "label": "Next »", "active": False}
        ],
        "next_page_url": next_url,
        "path": base_path,
        "per_page": per_page,
        "prev_page_url": prev_url,
        "to": min(offset + len(items), total_count),
        "total": total_count,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }
    
    if metrics is not None:
        response_data["metrics"] = metrics
    
    return response_data

async def paginate_simple(db: AsyncSession, query: Select, page: int = 1, per_page: int = 50, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page, per_page, offset = max(1, page), max(1, min(per_page, 100)), (max(1, page) - 1) * max(1, min(per_page, 100))
    result = await db.execute(query.offset(offset).limit(per_page + 1))
    items = result.scalars().all()
    has_next = len(items) > per_page
    if has_next: items = items[:-1]
    
    response_data = {
        "data": [await item.to_dict() if hasattr(item, 'to_dict') else item for item in items], 
        "current_page": page, 
        "per_page": per_page, 
        "has_next": has_next, 
        "has_prev": page > 1, 
        "count": len(items)
    }
    
    if metrics is not None:
        response_data["metrics"] = metrics
    
    return response_data

async def paginate_cursor(db: AsyncSession, query: Select, cursor_field: str, cursor_value: Optional[Any] = None, per_page: int = 50, direction: str = "next", metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    per_page = max(1, min(per_page, 100))
    if cursor_value is not None:
        model = query.column_descriptions[0]['type']
        cursor_column = getattr(model, cursor_field)
        query = query.where(cursor_column > cursor_value) if direction == "next" else query.where(cursor_column < cursor_value).order_by(cursor_column.desc())
    
    result = await db.execute(query.limit(per_page + 1))
    items = result.scalars().all()
    has_more = len(items) > per_page
    if has_more: items = items[:-1]
    
    next_cursor = getattr(items[-1], cursor_field) if items and has_more else None
    prev_cursor = getattr(items[0], cursor_field) if items else None
    
    response_data = {
        "data": [await item.to_dict() if hasattr(item, 'to_dict') else item for item in items], 
        "has_next": has_more, 
        "has_prev": cursor_value is not None, 
        "next_cursor": next_cursor, 
        "prev_cursor": prev_cursor, 
        "per_page": per_page, 
        "count": len(items)
    }
    
    if metrics is not None:
        response_data["metrics"] = metrics
    
    return response_data

class QueryOptimizer:
    @staticmethod
    def add_search_filter(query: Select, model, search: str, fields: List[str]) -> Select:
        return query.where(or_(*[getattr(model, field).ilike(f"%{search}%") for field in fields if hasattr(model, field)])) if search and fields else query
    
    @staticmethod
    def add_status_filter(query: Select, model, status: Optional[str], status_field: Optional[str] = "status") -> Select:
        return query.where(getattr(model, status_field) == status) if status and hasattr(model, status_field) else query
    
    @staticmethod
    def add_column_filter(query: Select, model, column_value: Optional[str], valid_value: Optional[str] = "", column_name: Optional[str] = "role") -> Select:
        return query.where(getattr(model, column_name) == column_value) if column_value and column_value == valid_value and hasattr(model, column_name) else query  