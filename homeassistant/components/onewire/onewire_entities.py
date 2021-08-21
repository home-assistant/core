"""Support for 1-Wire entities."""
from __future__ import annotations

import logging
from typing import Any

from pyownet import protocol

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import StateType

from .const import (
    SENSOR_TYPE_COUNT,
    SENSOR_TYPE_SENSED,
    SENSOR_TYPES,
    SWITCH_TYPE_LATCH,
    SWITCH_TYPE_PIO,
)
from .model import DeviceComponentDescription, OneWireEntityDescription

_LOGGER = logging.getLogger(__name__)


class OneWireBaseEntity(Entity):
    """Implementation of a 1-Wire entity."""

    def __init__(
        self,
        description: OneWireEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_unique_id = f"/{description.device_id}/{description.key}"
        self._attr_device_info = device_info
        self._state: StateType = None
        self._value_raw: float | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {
            "device_file": self.entity_description.device_file,
            "raw_value": self._value_raw,
        }


class OneWireProxyEntity(OneWireBaseEntity):
    """Implementation of a 1-Wire entity connected through owserver."""

    def __init__(
        self,
        description: OneWireEntityDescription,
        device_info: DeviceInfo,
        owproxy: protocol._Proxy,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            description=description,
            device_info=device_info,
        )
        self._owproxy = owproxy

    def _read_value_ownet(self) -> str:
        """Read a value from the owserver."""
        read_bytes: bytes = self._owproxy.read(self.entity_description.device_file)
        return read_bytes.decode().lstrip()

    def _write_value_ownet(self, value: bytes) -> None:
        """Write a value to the owserver."""
        self._owproxy.write(self.entity_description.device_file, value)

    def update(self) -> None:
        """Get the latest data from the device."""
        try:
            self._value_raw = float(self._read_value_ownet())
        except protocol.Error as exc:
            _LOGGER.error("Owserver failure in read(), got: %s", exc)
            self._state = None
        else:
            if self.entity_description.type == SENSOR_TYPE_COUNT:
                self._state = int(self._value_raw)
            elif self.entity_description.type in [
                SENSOR_TYPE_SENSED,
                SWITCH_TYPE_LATCH,
                SWITCH_TYPE_PIO,
            ]:
                self._state = int(self._value_raw) == 1
            else:
                self._state = round(self._value_raw, 1)
