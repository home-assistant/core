"""GE Home Sensor Entities - Freezer"""
import logging
from typing import Any, Dict, Optional

from gehomesdk import (
    ErdCode,
    ErdDoorStatus
)

from .ge_abstract_fridge import (
    ATTR_DOOR_STATUS, 
    HEATER_TYPE_FREEZER, 
    OP_MODE_TURBO_FREEZE,
    GeAbstractFridge
)

_LOGGER = logging.getLogger(__name__)

class GeFreezer(GeAbstractFridge):
    """A freezer is basically a fridge."""

    heater_type = HEATER_TYPE_FREEZER
    turbo_erd_code = ErdCode.TURBO_FREEZE_STATUS
    turbo_mode = OP_MODE_TURBO_FREEZE
    icon = "mdi:fridge-top"

    @property
    def door_state_attrs(self) -> Optional[Dict[str, Any]]:
        door_status = self.door_status.freezer
        if door_status and door_status != ErdDoorStatus.NA:
            return {ATTR_DOOR_STATUS: self._stringify(door_status)}
        return {}
