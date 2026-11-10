"""Admin panel API. One router, one module per section."""

from fastapi import APIRouter, Depends

from api.dependencies import require_admin

from . import access, data, models, settings, system, updates

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)], tags=["admin"])
router.include_router(updates.router)
router.include_router(settings.router)
router.include_router(models.router)
router.include_router(system.router)
router.include_router(access.router)
router.include_router(data.router)
