from fastapi import APIRouter
from app.apiv1.http.admin import AdminStationsController
from app.apiv1.http.admin import AdminHostsController
from app.apiv1.http.admin import AdminRadioProgramsController
from app.apiv1.http.admin import AdminStationScheduleController
from app.apiv1.http.admin import AdminNewsController
from app.apiv1.http.admin import AdminForumsController
from app.apiv1.http.admin import AdminAdvertsController
from app.apiv1.http.admin import AdminLiveChatController
from app.apiv1.http.admin import AdminEventsController
from app.apiv1.http.admin import AdminStatisticsController
from app.apiv1.http.admin import AdminRecordingBackgroundController

admin_routers = APIRouter()

admin_routers.include_router(AdminStatisticsController.router, prefix="/admin/statistics", tags=["Admin Statistics"])
admin_routers.include_router(AdminStationsController.router, prefix="/admin/stations", tags=["Admin Stations"])
admin_routers.include_router(AdminHostsController.router, prefix="/admin/hosts", tags=["Admin Hosts"])
admin_routers.include_router(AdminRadioProgramsController.router, prefix="/admin/radio_programs", tags=["Admin Radio Programs"])
admin_routers.include_router(AdminStationScheduleController.router, prefix="/admin/station_schedule", tags=["Admin Station Schedule"])
admin_routers.include_router(AdminNewsController.router, prefix="/admin/news", tags=["Admin News"])
admin_routers.include_router(AdminForumsController.router, prefix="/admin/forums", tags=["Admin Forums"])
admin_routers.include_router(AdminAdvertsController.router, prefix="/admin/adverts", tags=["Admin Adverts"])
admin_routers.include_router(AdminLiveChatController.router, prefix="/admin/livechat", tags=["Admin LiveChat"])
admin_routers.include_router(AdminEventsController.router, prefix="/admin/events", tags=["Admin Events"])
admin_routers.include_router(AdminRecordingBackgroundController.router, prefix="/admin/radio_sessions", tags=["Admin Radio Sessions"])
