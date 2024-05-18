"""Helper methods for Tado."""

from . import TadoConnector
from .const import (
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TIMER,
)


def decide_overlay_mode(
    tado: TadoConnector,
    duration: int | None,
    zone_id: int,
    overlay_mode: str | None = None,
) -> str:
    """Return correct overlay mode based on the action and defaults."""
    # If user gave duration then overlay mode needs to be timer
    if duration:
        return CONST_OVERLAY_TIMER
    # If no duration or timer set to fallback setting
    if overlay_mode is None:
        overlay_mode = tado.fallback or CONST_OVERLAY_TADO_MODE
    # If default is Tado default then look it up
    if overlay_mode == CONST_OVERLAY_TADO_DEFAULT:
        overlay_mode = (
            tado.data["zone"][zone_id].default_overlay_termination_type
            or CONST_OVERLAY_TADO_MODE
        )

    return overlay_mode
