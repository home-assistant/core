"""Support for ISY994 sensors."""
from __future__ import annotations

from typing import Any, cast

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as SENSOR, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_DOUBLE_TEMP,
    UOM_FRIENDLY_NAME,
    UOM_INDEX,
    UOM_ON_OFF,
    UOM_TO_STATES,
)
from .entity import ISYEntity, ISYNodeEntity
from .helpers import convert_isy_value_to_hass, migrate_old_unique_ids


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    entities: list[ISYSensorEntity | ISYSensorVariableEntity] = []

    for node in hass_isy_data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        entities.append(ISYSensorEntity(node))

    for vname, vobj in hass_isy_data[ISY994_VARIABLES]:
        entities.append(ISYSensorVariableEntity(vname, vobj))

    await migrate_old_unique_ids(hass, SENSOR, entities)
    async_add_entities(entities)


class ISYSensorEntity(ISYNodeEntity, SensorEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> dict | str | None:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom

        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return UOM_FRIENDLY_NAME.get(uom[0], uom[0])

        # Special cases for ISY UOM index units:
        if isy_states := UOM_TO_STATES.get(uom):
            return isy_states

        if uom in (UOM_ON_OFF, UOM_INDEX):
            assert isinstance(uom, str)
            return uom

        return UOM_FRIENDLY_NAME.get(uom)

    @property
    def native_value(self) -> float | int | str | None:
        """Get the state of the ISY994 sensor device."""
        if (value := self._node.status) == ISY_VALUE_UNKNOWN:
            return None

        # Get the translated ISY Unit of Measurement
        uom = self.raw_unit_of_measurement

        # Check if this is a known index pair UOM
        if isinstance(uom, dict):
            return uom.get(value, value)

        if uom in (UOM_INDEX, UOM_ON_OFF):
            return cast(str, self._node.formatted)

        # Check if this is an index type and get formatted value
        if uom == UOM_INDEX and hasattr(self._node, "formatted"):
            return cast(str, self._node.formatted)

        # Handle ISY precision and rounding
        value = convert_isy_value_to_hass(value, uom, self._node.prec)

        # Convert temperatures to Home Assistant's unit
        if uom in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            value = self.hass.config.units.temperature(value, uom)

        if value is None:
            return None

        assert isinstance(value, (int, float))
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Get the Home Assistant unit of measurement for the device."""
        raw_units = self.raw_unit_of_measurement
        # Check if this is a known index pair UOM
        if isinstance(raw_units, dict) or raw_units in (UOM_ON_OFF, UOM_INDEX):
            return None
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS, UOM_DOUBLE_TEMP):
            return self.hass.config.units.temperature_unit
        return raw_units


class ISYSensorVariableEntity(ISYEntity, SensorEntity):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._name = vname

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the variable."""
        return convert_isy_value_to_hass(self._node.status, "", self._node.prec)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get the state attributes for the device."""
        return {
            "init_value": convert_isy_value_to_hass(
                self._node.init, "", self._node.prec
            ),
            "last_edited": self._node.last_edited,
        }

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:counter"
