"""GE Home Sensor Entities - Fridge"""
import logging
from typing import Any, Dict

from gehomesdk import (
    ErdCode,
    ErdDoorStatus,
    ErdFilterStatus
)

from .const import *
from .ge_abstract_fridge import (
    ATTR_DOOR_STATUS,
    HEATER_TYPE_FRIDGE, 
    OP_MODE_TURBO_COOL,
    GeAbstractFridge
)

_LOGGER = logging.getLogger(__name__)

class GeFridge(GeAbstractFridge):
    heater_type = HEATER_TYPE_FRIDGE
    turbo_erd_code = ErdCode.TURBO_COOL_STATUS
    turbo_mode = OP_MODE_TURBO_COOL
    icon = "mdi:fridge-bottom"

    @property
    def other_state_attrs(self) -> Dict[str, Any]:
        if(self.api.has_erd_code(ErdCode.WATER_FILTER_STATUS)):
            filter_status: ErdFilterStatus = self.appliance.get_erd_value(ErdCode.WATER_FILTER_STATUS)
            if filter_status == ErdFilterStatus.NA:
                return {}
            return {"water_filter_status": self._stringify(filter_status)}
        return {}

    @property
    def door_state_attrs(self) -> Dict[str, Any]:
        """Get state attributes for the doors."""
        data = {}
        door_status = self.door_status
        if not door_status:
            return {}
        door_right = door_status.fridge_right
        door_left = door_status.fridge_left
        drawer = door_status.drawer

        if door_right and door_right != ErdDoorStatus.NA:
            data["right_door"] = door_status.fridge_right.name.title()
        if door_left and door_left != ErdDoorStatus.NA:
            data["left_door"] = door_status.fridge_left.name.title()
        if drawer and drawer != ErdDoorStatus.NA:
            data["drawer"] = door_status.drawer.name.title()

        if data:
            all_closed = all(v == "Closed" for v in data.values())
            data[ATTR_DOOR_STATUS] = "Closed" if all_closed else "Open"

        return data
