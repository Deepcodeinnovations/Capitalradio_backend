from fastapi import FastAPI, Request
from typing import Optional, List, TypeVar, Generic, Any, Dict
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from math import ceil
from starlette.requests import Request

# Define a generic type variable
T = TypeVar('T')

# Define the PaginationResponse model
class PaginationResponse(BaseModel, Generic[T]):
    data: Dict[str, Any]  # Use Dict from typing for compatibility
    msg: str
    status: str
    status_code: int

# Function to paginate data
def paginate_data(
    items: List[Any],
    page: Optional[int] = None,
    per_page: Optional[int] = None
) -> PaginationResponse:
    """
    Paginates a list of items and returns a PaginationResponse object.
    
    Args:
        items: The list of items to paginate.
        page: The current page number (defaults to 1).
        per_page: The number of items per page (defaults to 50).
    
    Returns:
        PaginationResponse: A response object containing paginated data.
    """
    # Set default values if None is provided
    page = 1 if page is None else max(1, page)
    per_page = 50 if per_page is None else max(1, per_page)
    base_url = ""  # Base URL for pagination links

    # Ensure we have valid integers
    try:
        page = int(page)
        per_page = int(per_page)
    except (TypeError, ValueError):
        page = 1
        per_page = 50

    # Calculate pagination values
    total_items = len(items)
    total_pages = max(1, ceil(total_items / per_page))

    # Ensure page doesn't exceed total pages
    page = min(page, total_pages)

    # Calculate indices for slicing the list
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    # Get current page items
    current_items = items[start_idx:end_idx]

    # Generate page links
    links = []

    # Previous page link
    prev_url = f"{base_url}?page={page-1}" if page > 1 else None
    links.append({
        "url": prev_url,
        "label": "« Previous",
        "active": False
    })

    # Current page link
    links.append({
        "url": f"{base_url}?page={page}",
        "label": str(page),
        "active": True
    })

    # Next page link
    next_url = f"{base_url}?page={page+1}" if page < total_pages else None
    links.append({
        "url": next_url,
        "label": "Next »",
        "active": False
    })

    # Construct pagination data
    pagination_data = {
        "current_page": page,
        "data": current_items,
        "first_page_url": f"{base_url}?page=1",
        "from": start_idx + 1 if current_items else 0,
        "last_page": total_pages,
        "last_page_url": f"{base_url}?page={total_pages}",
        "links": links,
        "next_page_url": next_url,
        "path": base_url,
        "per_page": per_page,
        "prev_page_url": prev_url,
        "to": min(end_idx, total_items),
        "total": total_items
    }

    # Return the pagination response
    return PaginationResponse(
        data=pagination_data,
        msg="Data fetched Successfully",
        status="success",
        status_code=200
    )

# Dependency to get the base URL
class BaseURLDependency:
    def __init__(self):
        self._request: Optional[Request] = None

    async def __call__(self, request: Request) -> str:
        """
        Returns the base URL for the request.
        
        Args:
            request: The incoming FastAPI request.
        
        Returns:
            str: The base URL.
        """
        self._request = request
        return f"{str(request.base_url)[:-1]}{request.url.path}"

# Create an instance of the dependency
get_base_url = BaseURLDependency()