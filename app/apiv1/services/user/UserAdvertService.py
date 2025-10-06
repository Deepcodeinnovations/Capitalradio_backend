from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, or_
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.AdvertModel import Advert
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from app.utils.file_upload import save_upload_file, remove_file
from app.utils.pagination import paginate_data
from fastapi.encoders import jsonable_encoder
import os
import uuid


async def get_user_adverts_by_station(db: AsyncSession, station_id: str, page: int = 1, per_page: int = 10) -> List[Advert]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(Advert).where(and_(Advert.station_id == station_id, Advert.state == True, Advert.status == True)).order_by(desc(Advert.created_at)).offset(offset).limit(per_page)
        result = await db.execute(stmt)
        adverts = result.scalars().all()
        adverts_data = [await advert.to_dict_with_relations(db) for advert in adverts]
        return paginate_data(jsonable_encoder(adverts_data), page=page, per_page=per_page)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch station adverts: {str(e)}")


