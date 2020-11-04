"""Support for 1-Wire entities."""
import logging
from typing import Any, Dict, Optional

from pyownet import protocol

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from .const import SENSOR_TYPE_COUNT, SENSOR_TYPE_SENSED, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


class OneWire(Entity):
    """Implementation of a 1-Wire sensor."""

    def __init__(
        self,
        name,
        device_file,
        sensor_type: str,
        sensor_name: str = None,
        device_info=None,
        default_disabled: bool = False,
    ):
        """Initialize the sensor."""
        self._name = f"{name} {sensor_name or sensor_type.capitalize()}"
        self._device_file = device_file
        self._sensor_type = sensor_type
        self._device_class = SENSOR_TYPES[sensor_type][1]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][0]
        self._device_info = device_info
        self._state = None
        self._value_raw = None
        self._default_disabled = default_disabled

    @property
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return {"device_file": self._device_file, "raw_value": self._value_raw}

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._device_file

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device specific attributes."""
        return self._device_info

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._default_disabled


class OneWireProxy(OneWire):
    """Implementation of a 1-Wire sensor through owserver."""

    def __init__(
        self,
        name: str,
        device_file: str,
        sensor_type: str,
        sensor_name: str,
        device_info: Dict[str, Any],
        default_disabled: bool,
        owproxy: protocol._Proxy,
    ):
        """Initialize the sensor."""
        super().__init__(
            name, device_file, sensor_type, sensor_name, device_info, default_disabled
        )
        self._owproxy = owproxy

    def _read_value_ownet(self):
        """Read a value from the owserver."""
        return self._owproxy.read(self._device_file).decode().lstrip()

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            self._value_raw = float(self._read_value_ownet())
        except protocol.Error as exc:
            _LOGGER.error("Owserver failure in read(), got: %s", exc)
        else:
            if self._sensor_type == SENSOR_TYPE_COUNT:
                value = int(self._value_raw)
            elif self._sensor_type == SENSOR_TYPE_SENSED:
                value = int(self._value_raw) == 1
            else:
                value = round(self._value_raw, 1)

        self._state = value
