from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from typing import Dict, Any, List
from decimal import Decimal
from app.models.StationModel import Station
from app.models.RadioProgramModel import RadioProgram
from app.models.HostModel import Host
from app.models.NewsModel import News
from app.models.EventModel import Event
from app.models.ForumModel import Forum
from app.models.AdvertModel import Advert
from app.models.RadioSessionRecordingModel import RadioSessionRecording
from app.models.LiveChatMessageModel import LiveChatMessage
from app.models.UserModel import User
import logging

logger = logging.getLogger(__name__)

def convert_decimal(value):
    """Convert Decimal to float for JSON serialization"""
    return float(value) if isinstance(value, Decimal) else value

async def get_dashboard_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        return {
            "overview": await _get_overview_stats(db),
            "stations": await _get_stations_analytics(db),
            "content": await _get_content_analytics(db),
            "engagement": await _get_engagement_analytics(db),
            "recordings": await _get_recordings_analytics(db),
            "users": await _get_users_analytics(db),
            "recent_activity": await _get_recent_activity(db),
            "trends": await _get_trends_analytics(db),
            "performance": await _get_performance_metrics(db)
        }
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def _get_overview_stats(db: AsyncSession) -> Dict[str, Any]:
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        queries = [
            select(func.count(Station.id)).where(Station.state == True),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.status == True)),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.streaming_status == 'live')),
            select(func.count(RadioProgram.id)).where(RadioProgram.state == True),
            select(func.count(Host.id)).where(Host.state == True),
            select(func.count(Host.id)).where(and_(Host.state == True, Host.on_air_status == True)),
            select(func.count(News.id)).where(News.state == True),
            select(func.count(News.id)).where(and_(News.state == True, News.is_published == True)),
            select(func.count(Event.id)).where(Event.state == True),
            select(func.count(User.id)).where(User.state == True),
            select(func.count(News.id)).where(and_(News.state == True, News.created_at >= week_ago)),
            select(func.count(Event.id)).where(and_(Event.state == True, Event.created_at >= week_ago))
        ]
        
        results = []
        for query in queries:
            result = await db.execute(query)
            results.append(result.scalar() or 0)
        
        return {
            "total_stations": results[0],
            "active_stations": results[1],
            "live_stations": results[2],
            "total_programs": results[3],
            "total_hosts": results[4],
            "on_air_hosts": results[5],
            "total_news": results[6],
            "published_news": results[7],
            "total_events": results[8],
            "total_users": results[9],
            "new_content_this_week": results[10],
            "new_events_this_week": results[11]
        }
    except Exception as e:
        logger.error(f"Error getting overview stats: {str(e)}")
        return {}

async def _get_stations_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        # Basic counts
        queries = [
            select(func.count(Station.id)).where(Station.state == True),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.status == True)),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.streaming_status == 'live')),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.streaming_status == 'offline')),
            select(func.count(Station.id)).where(and_(Station.state == True, Station.streaming_status == 'maintenance'))
        ]
        
        counts = []
        for query in queries:
            result = await db.execute(query)
            counts.append(result.scalar() or 0)
        
        # Station details
        stations_result = await db.execute(select(Station).where(and_(Station.state == True, Station.status == True)))
        stations = stations_result.scalars().all()
        
        station_details = []
        total_listeners = 0
        
        for station in stations:
            programs_count = await db.execute(select(func.count(RadioProgram.id)).where(and_(RadioProgram.station_id == station.id, RadioProgram.state == True)))
            news_count = await db.execute(select(func.count(News.id)).where(and_(News.station_id == station.id, News.state == True)))
            
            listeners = convert_decimal(station.listeners) if station.listeners else 0
            
            station_details.append({
                "id": station.id,
                "name": station.name,
                "frequency": station.frequency,
                "streaming_status": station.streaming_status,
                "listeners": listeners,
                "programs_count": programs_count.scalar() or 0,
                "news_count": news_count.scalar() or 0,
                "logo_url": station.logo_url
            })
            
            total_listeners += listeners
        
        return {
            "total_stations": counts[0],
            "active_stations": counts[1],
            "live_streaming": counts[2],
            "offline_stations": counts[3],
            "maintenance_stations": counts[4],
            "total_listeners": total_listeners,
            "station_details": station_details,
            "streaming_health": {
                "healthy": counts[2],
                "issues": counts[3] + counts[4]
            }
        }
    except Exception as e:
        logger.error(f"Error getting stations analytics: {str(e)}")
        return {}

async def _get_content_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        now = datetime.utcnow()
        
        # Content counts
        queries = [
            select(func.count(News.id)).where(News.state == True),
            select(func.count(News.id)).where(and_(News.state == True, News.is_published == True)),
            select(func.count(News.id)).where(and_(News.state == True, News.is_featured == True)),
            select(func.count(News.id)).where(and_(News.state == True, News.is_breaking == True)),
            select(func.count(Event.id)).where(Event.state == True),
            select(func.count(Event.id)).where(and_(Event.state == True, Event.is_published == True)),
            select(func.count(Event.id)).where(and_(Event.state == True, Event.is_featured == True)),
            select(func.count(Event.id)).where(and_(Event.state == True, Event.start_date >= now)),
            select(func.count(Forum.id)).where(Forum.state == True),
            select(func.count(Forum.id)).where(and_(Forum.state == True, Forum.is_published == True)),
            select(func.count(Forum.id)).where(and_(Forum.state == True, Forum.is_pinned == True)),
            select(func.count(Advert.id)).where(Advert.state == True),
            select(func.count(Advert.id)).where(and_(Advert.state == True, Advert.status == True))
        ]
        
        results = []
        for query in queries:
            result = await db.execute(query)
            results.append(result.scalar() or 0)
        
        # Top news
        top_news = await db.execute(
            select(News.title, News.views_count)
            .where(and_(News.state == True, News.is_published == True))
            .order_by(desc(News.views_count))
            .limit(5)
        )
        
        top_news_list = [{"title": row[0], "views": convert_decimal(row[1])} for row in top_news.fetchall()]
        
        return {
            "news": {
                "total": results[0],
                "published": results[1],
                "featured": results[2],
                "breaking": results[3],
                "top_articles": top_news_list
            },
            "events": {
                "total": results[4],
                "published": results[5],
                "featured": results[6],
                "upcoming": results[7]
            },
            "forums": {
                "total": results[8],
                "published": results[9],
                "pinned": results[10]
            },
            "adverts": {
                "total": results[11],
                "active": results[12]
            }
        }
    except Exception as e:
        logger.error(f"Error getting content analytics: {str(e)}")
        return {}

async def _get_engagement_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        today = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Chat analytics
        total_chat = await db.execute(select(func.count(LiveChatMessage.id)).where(LiveChatMessage.state == True))
        today_chat = await db.execute(select(func.count(LiveChatMessage.id)).where(and_(LiveChatMessage.state == True, LiveChatMessage.created_at >= today)))
        week_chat = await db.execute(select(func.count(LiveChatMessage.id)).where(and_(LiveChatMessage.state == True, LiveChatMessage.created_at >= week_ago)))
        
        # Station messages
        station_messages = await db.execute(
            select(Station.name, func.count(LiveChatMessage.id))
            .join(LiveChatMessage, Station.id == LiveChatMessage.station_id)
            .where(and_(Station.state == True, LiveChatMessage.state == True))
            .group_by(Station.id, Station.name)
        )
        
        # News engagement
        news_views = await db.execute(select(func.sum(News.views_count)).where(and_(News.state == True, News.is_published == True)))
        news_likes = await db.execute(select(func.sum(News.likes_count)).where(and_(News.state == True, News.is_published == True)))
        news_shares = await db.execute(select(func.sum(News.shares_count)).where(and_(News.state == True, News.is_published == True)))
        
        return {
            "chat": {
                "total_messages": total_chat.scalar() or 0,
                "today_messages": today_chat.scalar() or 0,
                "week_messages": week_chat.scalar() or 0,
                "by_station": [{"station": row[0], "messages": row[1]} for row in station_messages.fetchall()]
            },
            "news_engagement": {
                "total_views": convert_decimal(news_views.scalar()) if news_views.scalar() else 0,
                "total_likes": convert_decimal(news_likes.scalar()) if news_likes.scalar() else 0,
                "total_shares": convert_decimal(news_shares.scalar()) if news_shares.scalar() else 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting engagement analytics: {str(e)}")
        return {}

async def _get_recordings_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        # Recording counts by status
        statuses = ['scheduled', 'recording', 'completed', 'failed']
        counts = {}
        
        total_result = await db.execute(select(func.count(RadioSessionRecording.id)).where(RadioSessionRecording.state == True))
        counts['total'] = total_result.scalar() or 0
        
        for status in statuses:
            result = await db.execute(
                select(func.count(RadioSessionRecording.id)).where(
                    and_(RadioSessionRecording.state == True, RadioSessionRecording.recording_status == status)
                )
            )
            counts[status] = result.scalar() or 0
        
        # Storage size
        storage_result = await db.execute(
            select(func.sum(RadioSessionRecording.file_size_mb)).where(
                and_(RadioSessionRecording.state == True, RadioSessionRecording.recording_status == 'completed')
            )
        )
        
        # Recent recordings
        recent = await db.execute(
            select(RadioSessionRecording.id, RadioSessionRecording.recording_status, 
                   RadioSessionRecording.scheduled_start_time, Station.name)
            .join(Station, RadioSessionRecording.station_id == Station.id)
            .where(RadioSessionRecording.state == True)
            .order_by(desc(RadioSessionRecording.created_at))
            .limit(10)
        )
        
        recent_list = []
        for row in recent.fetchall():
            recent_list.append({
                "id": row[0],
                "status": row[1],
                "scheduled_time": row[2].isoformat() if row[2] else None,
                "station_name": row[3]
            })
        
        success_rate = round((counts['completed'] / max(counts['total'], 1)) * 100, 2) if counts['total'] > 0 else 0
        
        return {
            "total_recordings": counts['total'],
            "scheduled": counts['scheduled'],
            "active": counts['recording'],
            "completed": counts['completed'],
            "failed": counts['failed'],
            "total_storage_mb": convert_decimal(storage_result.scalar()) if storage_result.scalar() else 0,
            "recent_recordings": recent_list,
            "success_rate": success_rate
        }
    except Exception as e:
        logger.error(f"Error getting recordings analytics: {str(e)}")
        return {}

async def _get_users_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        queries = [
            select(func.count(User.id)).where(User.state == True),
            select(func.count(User.id)).where(and_(User.state == True, User.status == True)),
            select(func.count(User.id)).where(and_(User.state == True, User.last_seen >= week_ago)),
            select(func.count(User.id)).where(and_(User.state == True, User.role == 'admin')),
            select(func.count(User.id)).where(and_(User.state == True, User.role == 'editor')),
            select(func.count(User.id)).where(and_(User.state == True, User.role == 'presenter'))
        ]
        
        results = []
        for query in queries:
            result = await db.execute(query)
            results.append(result.scalar() or 0)
        
        return {
            "total_users": results[0],
            "active_users": results[1],
            "recent_active": results[2],
            "by_role": {
                "admin": results[3],
                "editor": results[4],
                "presenter": results[5]
            }
        }
    except Exception as e:
        logger.error(f"Error getting users analytics: {str(e)}")
        return {}

async def _get_recent_activity(db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        activities = []
        
        # Recent news
        recent_news = await db.execute(
            select(News.title, News.created_at, User.name)
            .join(User, News.author_id == User.id)
            .where(News.state == True)
            .order_by(desc(News.created_at))
            .limit(5)
        )
        
        for row in recent_news.fetchall():
            activities.append({
                "type": "news",
                "title": row[0],
                "timestamp": row[1].isoformat(),
                "user": row[2],
                "action": "created article"
            })
        
        # Recent events
        recent_events = await db.execute(
            select(Event.title, Event.created_at, User.name)
            .join(User, Event.created_by == User.id)
            .where(Event.state == True)
            .order_by(desc(Event.created_at))
            .limit(5)
        )
        
        for row in recent_events.fetchall():
            activities.append({
                "type": "event",
                "title": row[0],
                "timestamp": row[1].isoformat(),
                "user": row[2],
                "action": "created event"
            })
        
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:10]
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return []

async def _get_trends_analytics(db: AsyncSession) -> Dict[str, Any]:
    try:
        trends = {"daily_content": []}
        
        for i in range(7):
            date = datetime.utcnow() - timedelta(days=i)
            date_start = datetime.combine(date.date(), datetime.min.time())
            date_end = datetime.combine(date.date(), datetime.max.time())
            
            news_count = await db.execute(
                select(func.count(News.id)).where(
                    and_(News.state == True, News.created_at.between(date_start, date_end))
                )
            )
            
            events_count = await db.execute(
                select(func.count(Event.id)).where(
                    and_(Event.state == True, Event.created_at.between(date_start, date_end))
                )
            )
            
            trends["daily_content"].append({
                "date": date.strftime("%Y-%m-%d"),
                "news": news_count.scalar() or 0,
                "events": events_count.scalar() or 0
            })
        
        trends["daily_content"].reverse()
        return trends
    except Exception as e:
        logger.error(f"Error getting trends analytics: {str(e)}")
        return {}

async def _get_performance_metrics(db: AsyncSession) -> Dict[str, Any]:
    try:
        # Count records
        stations_count = await db.execute(select(func.count(Station.id)).where(Station.state == True))
        programs_count = await db.execute(select(func.count(RadioProgram.id)).where(RadioProgram.state == True))
        news_count = await db.execute(select(func.count(News.id)).where(News.state == True))
        events_count = await db.execute(select(func.count(Event.id)).where(Event.state == True))
        
        total_records = (
            (stations_count.scalar() or 0) +
            (programs_count.scalar() or 0) +
            (news_count.scalar() or 0) +
            (events_count.scalar() or 0)
        )
        
        # Health ratios
        published_news_ratio = 0
        if news_count.scalar():
            published_news = await db.execute(
                select(func.count(News.id)).where(and_(News.state == True, News.is_published == True))
            )
            published_news_ratio = (published_news.scalar() or 0) / news_count.scalar() * 100
        
        station_health = 0
        if stations_count.scalar():
            active_stations = await db.execute(
                select(func.count(Station.id)).where(and_(Station.state == True, Station.status == True))
            )
            station_health = (active_stations.scalar() or 0) / stations_count.scalar() * 100
        
        return {
            "total_records": total_records,
            "content_health": {
                "published_news_ratio": round(published_news_ratio, 2),
                "station_health": round(station_health, 2)
            },
            "system_status": "healthy" if station_health > 80 else "warning" if station_health > 50 else "critical"
        }
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        return {}