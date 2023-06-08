"""Tuya Home Assistant Base Device Model."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import struct
from typing import Any, Literal, overload

from tuya_iot import TuyaDevice, TuyaDeviceManager
from typing_extensions import Self

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, LOGGER, TUYA_HA_SIGNAL_UPDATE_ENTITY, DPCode, DPType
from .util import remap_value


@dataclass
class IntegerTypeData:
    """Integer Type Data."""

    dpcode: DPCode
    min: int
    max: int
    scale: float
    step: float
    unit: str | None = None
    type: str | None = None

    @property
    def max_scaled(self) -> float:
        """Return the max scaled."""
        return self.scale_value(self.max)

    @property
    def min_scaled(self) -> float:
        """Return the min scaled."""
        return self.scale_value(self.min)

    @property
    def step_scaled(self) -> float:
        """Return the step scaled."""
        return self.step / (10**self.scale)

    def scale_value(self, value: float | int) -> float:
        """Scale a value."""
        return value / (10**self.scale)

    def scale_value_back(self, value: float | int) -> int:
        """Return raw value for scaled."""
        return int(value * (10**self.scale))

    def remap_value_to(
        self,
        value: float,
        to_min: float | int = 0,
        to_max: float | int = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from this range to a new range."""
        return remap_value(value, self.min, self.max, to_min, to_max, reverse)

    def remap_value_from(
        self,
        value: float,
        from_min: float | int = 0,
        from_max: float | int = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from its current range to this range."""
        return remap_value(value, from_min, from_max, self.min, self.max, reverse)

    @classmethod
    def from_json(cls, dpcode: DPCode, data: str) -> IntegerTypeData | None:
        """Load JSON string and return a IntegerTypeData object."""
        if not (parsed := json.loads(data)):
            return None

        return cls(
            dpcode,
            min=int(parsed["min"]),
            max=int(parsed["max"]),
            scale=float(parsed["scale"]),
            step=max(float(parsed["step"]), 1),
            unit=parsed.get("unit"),
            type=parsed.get("type"),
        )


@dataclass
class EnumTypeData:
    """Enum Type Data."""

    dpcode: DPCode
    range: list[str]

    @classmethod
    def from_json(cls, dpcode: DPCode, data: str) -> EnumTypeData | None:
        """Load JSON string and return a EnumTypeData object."""
        if not (parsed := json.loads(data)):
            return None
        return cls(dpcode, **parsed)


@dataclass
class ElectricityTypeData:
    """Electricity Type Data."""

    electriccurrent: str | None = None
    power: str | None = None
    voltage: str | None = None

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Load JSON string and return a ElectricityTypeData object."""
        return cls(**json.loads(data.lower()))

    @classmethod
    def from_raw(cls, data: str) -> Self:
        """Decode base64 string and return a ElectricityTypeData object."""
        raw = base64.b64decode(data)
        voltage = struct.unpack(">H", raw[0:2])[0] / 10.0
        electriccurrent = struct.unpack(">L", b"\x00" + raw[2:5])[0] / 1000.0
        power = struct.unpack(">L", b"\x00" + raw[5:8])[0] / 1000.0
        return cls(
            electriccurrent=str(electriccurrent), power=str(power), voltage=str(voltage)
        )


class TuyaEntity(Entity):
    """Tuya base device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init TuyaHaEntity."""
        self._attr_unique_id = f"tuya.{device.id}"
        self.device = device
        self.device_manager = device_manager

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="Tuya",
            name=self.device.name,
            model=f"{self.device.product_name} ({self.device.product_id})",
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
    ) -> EnumTypeData | None:
        ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[DPType.INTEGER],
    ) -> IntegerTypeData | None:
        ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> DPCode | None:
        ...

    def find_dpcode(
        self,
        dpcodes: str | DPCode | tuple[DPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: DPType | None = None,
    ) -> DPCode | EnumTypeData | IntegerTypeData | None:
        """Find a matching DP code available on for this device."""
        if dpcodes is None:
            return None

        if isinstance(dpcodes, str):
            dpcodes = (DPCode(dpcodes),)
        elif not isinstance(dpcodes, tuple):
            dpcodes = (dpcodes,)

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]

        # When we are not looking for a specific datatype, we can append status for
        # searching
        if not dptype:
            order.append("status")

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

                if dptype not in (DPType.ENUM, DPType.INTEGER):
                    return dpcode

        return None

    def get_dptype(
        self, dpcode: DPCode | None, prefer_function: bool = False
    ) -> DPType | None:
        """Find a matching DPCode data type available on for this device."""
        if dpcode is None:
            return None

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]
        for key in order:
            if dpcode in getattr(self.device, key):
                return DPType(getattr(self.device, key)[dpcode].type)

        return None

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.device.id}",
                self.async_write_ha_state,
            )
        )

    def _send_command(self, commands: list[dict[str, Any]]) -> None:
        """Send command to the device."""
        LOGGER.debug("Sending commands for device %s: %s", self.device.id, commands)
        self.device_manager.send_commands(self.device.id, commands)
