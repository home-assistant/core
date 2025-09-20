"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

from typing import Any, Literal, overload

from tuya_sharing import CustomerDevice, Manager

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER, TUYA_HA_SIGNAL_UPDATE_ENTITY, DPCode, DPType
from .models import EnumTypeData, IntegerTypeData

_DPTYPE_MAPPING: dict[str, DPType] = {
    "bitmap": DPType.BITMAP,
    "bool": DPType.BOOLEAN,
    "enum": DPType.ENUM,
    "json": DPType.JSON,
    "raw": DPType.RAW,
    "string": DPType.STRING,
    "value": DPType.INTEGER,
}


class TuyaEntity(Entity):
    """Tuya base device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Init TuyaHaEntity."""
        self._attr_unique_id = f"tuya.{device.id}"
        # TuyaEntity initialize mq can subscribe
        device.set_up = True
        self.device = device
        self.device_manager = device_manager

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="Tuya",
            name=self.device.name,
            model=self.device.product_name,
            model_id=self.device.product_id,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device.online

    @overload
    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[DPType.ENUM],
    ) -> EnumTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[DPType.INTEGER],
    ) -> IntegerTypeData | None: ...

    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: DPType,
    ) -> EnumTypeData | IntegerTypeData | None:
        """Find type information for a matching DP code available for this device."""
        if dptype not in (DPType.ENUM, DPType.INTEGER):
            raise NotImplementedError("Only ENUM and INTEGER types are supported")

        if dpcodes is None:
            return None

        if isinstance(dpcodes, str):
            dpcodes = (DPCode(dpcodes),)
        elif not isinstance(dpcodes, tuple):
            dpcodes = (dpcodes,)

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]

        for dpcode in dpcodes:
            for key in order:
                if dpcode not in getattr(self.device, key):
                    continue
                if (
                    dptype == DPType.ENUM
                    and getattr(self.device, key)[dpcode].type == DPType.ENUM
                ):
                    if not (
                        enum_type := EnumTypeData.from_json(
                            dpcode, getattr(self.device, key)[dpcode].values
                        )
                    ):
                        continue
                    return enum_type

                if (
                    dptype == DPType.INTEGER
                    and getattr(self.device, key)[dpcode].type == DPType.INTEGER
                ):
                    if not (
                        integer_type := IntegerTypeData.from_json(
                            dpcode, getattr(self.device, key)[dpcode].values
                        )
                    ):
                        continue
                    return integer_type

        return None

    def get_dptype(
        self, dpcode: DPCode | None, *, prefer_function: bool = False
    ) -> DPType | None:
        """Find a matching DPCode data type available on for this device."""
        if dpcode is None:
            return None

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]
        for key in order:
            if dpcode in getattr(self.device, key):
                current_type = getattr(self.device, key)[dpcode].type
                try:
                    return DPType(current_type)
                except ValueError:
                    # Sometimes, we get ill-formed DPTypes from the cloud,
                    # this fixes them and maps them to the correct DPType.
                    return _DPTYPE_MAPPING.get(current_type)

        return None

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.device.id}",
                self._handle_state_update,
            )
        )

    async def _handle_state_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict | None = None,
    ) -> None:
        self.async_write_ha_state()

    def _send_command(self, commands: list[dict[str, Any]]) -> None:
        """Send command to the device."""
        LOGGER.debug("Sending commands for device %s: %s", self.device.id, commands)
        self.device_manager.send_commands(self.device.id, commands)
