from sqlalchemy import Boolean, Column, String, DateTime, event, or_, and_
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
import uuid
import json


T = TypeVar('T', bound='BaseModelMixin')

def generate_uuid() -> str:
    return str(uuid.uuid4())

def generate_wallet_reference() -> str:
    return f"W-{uuid.uuid4().hex[:10].upper()}"

class BaseModelMixin:
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    state = Column(Boolean, default=True, nullable=False)
    status = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def __declare_last__(cls):
        @event.listens_for(cls, 'before_insert')
        def receive_before_insert(mapper, connection, instance):
            if instance.id is None:
                instance.id = generate_uuid()

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        if exclude is None:
            exclude = []
            
        data = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    data[column.name] = value.isoformat()
                else:
                    data[column.name] = value
        return data

    def to_json(self, exclude: Optional[List[str]] = None) -> str:
        return json.dumps(self.to_dict(exclude))

    # CRUD Class Methods
    @classmethod
    def create(cls: Type[T], db: Session, **kwargs) -> T:
        instance = cls(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    @classmethod
    def get_by_id(cls: Type[T], db: Session, id: str) -> Optional[T]:
        return db.query(cls).filter(cls.id == id, cls.state == True).first()

    @classmethod
    def get_all(
        cls: Type[T], 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        query = db.query(cls).filter(cls.state == True)
        
        if filters:
            filter_conditions = []
            for key, value in filters.items():
                if hasattr(cls, key):
                    filter_conditions.append(getattr(cls, key) == value)
            if filter_conditions:
                query = query.filter(and_(*filter_conditions))
                
        return query.offset(skip).limit(limit).all()

    @classmethod
    def search(
        cls: Type[T], 
        db: Session, 
        search_term: str,
        fields: List[str],
        skip: int = 0,
        limit: int = 100
    ) -> List[T]:

        conditions = []
        for field in fields:
            if hasattr(cls, field):
                conditions.append(getattr(cls, field).ilike(f"%{search_term}%"))
        
        return db.query(cls)\
            .filter(cls.state == True)\
            .filter(or_(*conditions))\
            .offset(skip)\
            .limit(limit)\
            .all()

    # Instance Methods
    def update(self, db: Session, **kwargs) -> T:

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> None:
        self.state = False
        db.commit()

    def hard_delete(self, db: Session) -> None:
        db.delete(self)
        db.commit()

    def restore(self, db: Session) -> T:
        self.state = True
        db.commit()
        db.refresh(self)
        return self

    def toggle_status(self, db: Session) -> T:
        self.status = not self.status
        db.commit()
        db.refresh(self)
        return self
    

Base = declarative_base(cls=BaseModelMixin)