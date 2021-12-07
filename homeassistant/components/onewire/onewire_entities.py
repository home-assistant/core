"""Support for 1-Wire entities."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from pyownet import protocol

from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.typing import StateType

from .const import READ_MODE_BOOL, READ_MODE_INT


@dataclass
class OneWireEntityDescription(EntityDescription):
    """Class describing OneWire entities."""

    read_mode: str | None = None


_LOGGER = logging.getLogger(__name__)


class OneWireBaseEntity(Entity):
    """Implementation of a 1-Wire entity."""

    entity_description: OneWireEntityDescription

    def __init__(
        self,
        description: OneWireEntityDescription,
        device_id: str,
        device_info: DeviceInfo,
        device_file: str,
        name: str,
        *,
        rounding: int | None = None,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_unique_id = f"/{device_id}/{description.key}"
        self._attr_device_info = device_info
        self._attr_extra_state_attributes = {"device_file": device_file}
        self._attr_name = name
        self._device_file = device_file
        self._state: StateType = None
        self._rounding = rounding


class OneWireProxyEntity(OneWireBaseEntity):
    """Implementation of a 1-Wire entity connected through owserver."""

    def __init__(
        self,
        description: OneWireEntityDescription,
        device_id: str,
        device_info: DeviceInfo,
        device_file: str,
        name: str,
        owproxy: protocol._Proxy,
        rounding: int | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            description=description,
            device_id=device_id,
            device_info=device_info,
            device_file=device_file,
            name=name,
            rounding=rounding,
        )
        self._owproxy = owproxy

    def _read_value_ownet(self) -> str:
        """Read a value from the owserver."""
        read_bytes: bytes = self._owproxy.read(self._device_file)
        return read_bytes.decode().lstrip()

    def _write_value_ownet(self, value: bytes) -> None:
        """Write a value to the owserver."""
        self._owproxy.write(self._device_file, value)

    def update(self) -> None:
        """Get the latest data from the device."""
        try:
            raw_value = float(self._read_value_ownet())
        except protocol.Error as exc:
            _LOGGER.error("Owserver failure in read(), got: %s", exc)
            self._state = None
        else:
            if self.entity_description.read_mode == READ_MODE_INT:
                self._state = int(raw_value)
            elif self.entity_description.read_mode == READ_MODE_BOOL:
                self._state = int(raw_value) == 1
            else:
                if self._rounding is not None:
                    raw_value = round(raw_value, self._rounding)
                self._state = raw_value
