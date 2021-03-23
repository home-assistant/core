"""Support for 1-Wire entities."""
from __future__ import annotations

import logging
from typing import Any

from pyownet import protocol

from homeassistant.helpers.entity import Entity

from .const import (
    SENSOR_TYPE_COUNT,
    SENSOR_TYPE_SENSED,
    SENSOR_TYPES,
    SWITCH_TYPE_LATCH,
    SWITCH_TYPE_PIO,
)

_LOGGER = logging.getLogger(__name__)


class OneWireBaseEntity(Entity):
    """Implementation of a 1-Wire entity."""

    def __init__(
        self,
        name,
        device_file,
        entity_type: str,
        entity_name: str = None,
        device_info=None,
        default_disabled: bool = False,
        unique_id: str = None,
    ):
        """Initialize the entity."""
        self._name = f"{name} {entity_name or entity_type.capitalize()}"
        self._device_file = device_file
        self._entity_type = entity_type
        self._device_class = SENSOR_TYPES[entity_type][1]
        self._unit_of_measurement = SENSOR_TYPES[entity_type][0]
        self._device_info = device_info
        self._state = None
        self._value_raw = None
        self._default_disabled = default_disabled
        self._unique_id = unique_id or device_file

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._name

    @property
    def device_class(self) -> str | None:
        """Return the class of this device."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {"device_file": self._device_file, "raw_value": self._value_raw}

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device specific attributes."""
        return self._device_info

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._default_disabled


class OneWireProxyEntity(OneWireBaseEntity):
    """Implementation of a 1-Wire entity connected through owserver."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        device_info: dict[str, Any],
        entity_path: str,
        entity_specs: dict[str, Any],
        owproxy: protocol._Proxy,
    ):
        """Initialize the sensor."""
        super().__init__(
            name=device_name,
            device_file=entity_path,
            entity_type=entity_specs["type"],
            entity_name=entity_specs["name"],
            device_info=device_info,
            default_disabled=entity_specs.get("default_disabled", False),
            unique_id=f"/{device_id}/{entity_specs['path']}",
        )
        self._owproxy = owproxy

    def _read_value_ownet(self):
        """Read a value from the owserver."""
        return self._owproxy.read(self._device_file).decode().lstrip()

    def _write_value_ownet(self, value: bytes):
        """Write a value to the owserver."""
        return self._owproxy.write(self._device_file, value)

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            self._value_raw = float(self._read_value_ownet())
        except protocol.Error as exc:
            _LOGGER.error("Owserver failure in read(), got: %s", exc)
        else:
            if self._entity_type == SENSOR_TYPE_COUNT:
                value = int(self._value_raw)
            elif self._entity_type in [
                SENSOR_TYPE_SENSED,
                SWITCH_TYPE_LATCH,
                SWITCH_TYPE_PIO,
            ]:
                value = int(self._value_raw) == 1
            else:
                value = round(self._value_raw, 1)

        self._state = value
