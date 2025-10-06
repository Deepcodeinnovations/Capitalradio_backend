from typing import Optional, List, Any, Dict, Callable
from math import ceil
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy import func, or_
import asyncio

def create_pagination_response(items: List[Any], current_page: int, per_page: int, total: Optional[int] = None, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    offset = (current_page - 1) * per_page
    from_item = offset + 1 if items else 0
    to_item = offset + len(items)
    
    if total is not None:
        total_pages = max(1, ceil(total / per_page))
        has_next = current_page < total_pages
        has_prev = current_page > 1
        last_page = total_pages
    else:
        has_next = len(items) > per_page
        has_prev = current_page > 1
        last_page = current_page + 1 if has_next else current_page
        total_pages = last_page
    
    response_data = {"current_page": current_page, "data": items, "from": from_item, "last_page": last_page, "per_page": per_page, "to": to_item, "has_next": has_next, "has_prev": has_prev, "count": len(items)}
    
    if total is not None: response_data.update({"total": total, "total_pages": total_pages})
    if metrics is not None: response_data["metrics"] = metrics
    
    return response_data

async def paginate_query(db: AsyncSession, query: Select, page: int = 1, per_page: int = 50, transform_func: Optional[Callable] = None, include_total: bool = True, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page, per_page = max(1, page), max(1, min(per_page, 100))
    offset = (page - 1) * per_page
    
    total = None
    if include_total:
        try: total = (await db.execute(query.with_only_columns(func.count()).order_by(None))).scalar() or 0
        except: include_total = False
    
    result = await db.execute(query.offset(offset).limit(per_page + 1))
    items = result.scalars().all()
    has_more_items = len(items) > per_page
    if has_more_items: items = items[:-1]
    
    if transform_func:
        try: items = [await transform_func(item, db) if asyncio.iscoroutinefunction(transform_func) else transform_func(item, db) for item in items]
        except Exception as e: print(f"Transform function failed: {e}")
    
    estimated_total = (offset + len(items) + 1 if has_more_items else offset + len(items)) if not include_total else total
    
    return create_pagination_response(items=items, current_page=page, per_page=per_page, total=estimated_total if include_total else None, metrics=metrics)

def paginate_data(items: List[Any], total_count: int, page: Optional[int] = 1, per_page: Optional[int] = 50, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page = max(1, page or 1)
    per_page = max(1, min(per_page or 50, 100))
    return create_pagination_response(items=items, current_page=page, per_page=per_page, total=total_count, metrics=metrics)

async def paginate_simple(db: AsyncSession, query: Select, page: int = 1, per_page: int = 50, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page, per_page = max(1, page), max(1, min(per_page, 100))
    offset = (page - 1) * per_page
    
    result = await db.execute(query.offset(offset).limit(per_page + 1))
    items = result.scalars().all()
    has_more_items = len(items) > per_page
    if has_more_items: items = items[:-1]
    
    transformed_items = []
    for item in items:
        try:
            if hasattr(item, 'to_dict'): transformed_items.append(await item.to_dict() if asyncio.iscoroutinefunction(item.to_dict) else item.to_dict())
            else: transformed_items.append(item)
        except: transformed_items.append(item)
    
    return create_pagination_response(items=transformed_items, current_page=page, per_page=per_page, total=None, metrics=metrics)


async def paginate_cursor(db: AsyncSession, query: Select, cursor_field: str, cursor_value: Optional[Any] = None, per_page: int = 50, direction: str = "next", transform_func: Optional[Callable] = None,  metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    per_page = max(1, min(per_page, 100))
    
    if cursor_value is not None:
        try:
            model = query.column_descriptions[0]['type'] if hasattr(query, 'column_descriptions') and query.column_descriptions else query.froms[0].entity_zero_or_selectable
            cursor_column = getattr(model, cursor_field)
            query = query.where(cursor_column > cursor_value) if direction == "next" else query.where(cursor_column < cursor_value).order_by(cursor_column.desc())
        except (AttributeError, IndexError): pass
    
    result = await db.execute(query.limit(per_page + 1))
    items = result.scalars().all()
    has_more = len(items) > per_page
    if has_more: items = items[:-1]
    
    # FIX: Proper datetime serialization in transform
    from datetime import datetime
    transformed_items = []
    try: transformed_items = [await transform_func(item, db) if asyncio.iscoroutinefunction(transform_func) else transform_func(item, db) for item in items]
    except Exception as e: print(f"Transform function failed: {e}")
    
    next_cursor = prev_cursor = None
    if items:
        try:
            if has_more:
                cursor_val = getattr(items[-1], cursor_field)
                next_cursor = cursor_val.isoformat() if isinstance(cursor_val, datetime) else cursor_val  # ✅ FIX
            if cursor_value is not None:
                cursor_val = getattr(items[0], cursor_field)
                prev_cursor = cursor_val.isoformat() if isinstance(cursor_val, datetime) else cursor_val  # ✅ FIX
        except AttributeError: pass
    
    response_data = create_pagination_response(items=transformed_items, current_page=1, per_page=per_page, total=None, metrics=metrics)
    response_data.update({"has_more": has_more, "next_cursor": next_cursor, "prev_cursor": prev_cursor, "cursor_field": cursor_field, "direction": direction})
    for key in ["current_page", "last_page", "from", "to"]: response_data.pop(key, None)
    
    return response_data

class QueryOptimizer:
    @staticmethod
    def add_search_filter(query: Select, model, search: str, fields: List[str]) -> Select:
        if not search or not fields: return query
        search_conditions = [getattr(model, field).ilike(f"%{search}%") for field in fields if hasattr(model, field)]
        return query.where(or_(*search_conditions)) if search_conditions else query
    
    @staticmethod
    def add_status_filter(query: Select, model, status: Optional[str], status_field: Optional[str] = "status") -> Select:
        return query.where(getattr(model, status_field) == status) if status and status_field and hasattr(model, status_field) else query
    
    @staticmethod
    def add_column_filter(query: Select, model, column_value: Optional[str], valid_value: Optional[str] = "", column_name: Optional[str] = "role") -> Select:
        return query.where(getattr(model, column_name) == column_value) if column_value and column_value == valid_value and column_name and hasattr(model, column_name) else query
    
    @staticmethod
    def add_multiple_filters(query: Select, model, filters: Dict[str, Any]) -> Select:
        for field, value in filters.items():
            if value is not None and hasattr(model, field):
                try:
                    column = getattr(model, field)
                    query = query.where(column.in_(value)) if isinstance(value, list) else query.where(column == value)
                except AttributeError: continue
        return query