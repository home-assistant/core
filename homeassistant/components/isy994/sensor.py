"""Support for ISY994 sensors."""
from __future__ import annotations

from typing import Any, cast

from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    ISY_VALUE_UNKNOWN,
    PROP_BATTERY_LEVEL,
    PROP_BUSY,
    PROP_COMMS_ERROR,
    PROP_ENERGY_MODE,
    PROP_HEAT_COOL_STATE,
    PROP_HUMIDITY,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    PROP_TEMPERATURE,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node

from homeassistant.components.sensor import (
    DOMAIN as SENSOR,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    SENSOR_AUX,
    UOM_DOUBLE_TEMP,
    UOM_FRIENDLY_NAME,
    UOM_INDEX,
    UOM_ON_OFF,
    UOM_TO_STATES,
)
from .entity import ISYEntity, ISYNodeEntity
from .helpers import convert_isy_value_to_hass, migrate_old_unique_ids

# Disable general purpose and redundant sensors by default
AUX_DISABLED_BY_DEFAULT_MATCH = ["GV", "DO"]
AUX_DISABLED_BY_DEFAULT_EXACT = {
    PROP_ENERGY_MODE,
    PROP_HEAT_COOL_STATE,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
}
SKIP_AUX_PROPERTIES = {PROP_BUSY, PROP_COMMS_ERROR, PROP_STATUS}

ISY_CONTROL_TO_DEVICE_CLASS = {
    PROP_BATTERY_LEVEL: SensorDeviceClass.BATTERY,
    PROP_HUMIDITY: SensorDeviceClass.HUMIDITY,
    PROP_TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    "BARPRES": SensorDeviceClass.PRESSURE,
    "CO2LVL": SensorDeviceClass.CO2,
    "CV": SensorDeviceClass.VOLTAGE,
    "LUMIN": SensorDeviceClass.ILLUMINANCE,
    "PF": SensorDeviceClass.POWER_FACTOR,
}
ISY_CONTROL_TO_STATE_CLASS = {
    control: SensorStateClass.MEASUREMENT for control in ISY_CONTROL_TO_DEVICE_CLASS
}
ISY_CONTROL_TO_ENTITY_CATEGORY = {
    PROP_RAMP_RATE: EntityCategory.CONFIG,
    PROP_ON_LEVEL: EntityCategory.CONFIG,
    PROP_COMMS_ERROR: EntityCategory.DIAGNOSTIC,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    entities: list[ISYSensorEntity | ISYSensorVariableEntity] = []

    for node in hass_isy_data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        entities.append(ISYSensorEntity(node))

    aux_nodes = set()
    for node, control in hass_isy_data[ISY994_NODES][SENSOR_AUX]:
        aux_nodes.add(node)
        if control in SKIP_AUX_PROPERTIES:
            continue
        _LOGGER.debug("Loading %s %s", node.name, node.aux_properties[control])
        enabled_default = control not in AUX_DISABLED_BY_DEFAULT_EXACT and not any(
            control.startswith(match) for match in AUX_DISABLED_BY_DEFAULT_MATCH
        )
        entities.append(ISYAuxSensorEntity(node, control, enabled_default))

    for node in aux_nodes:
        # Any node in SENSOR_AUX can potentially have communication errors
        entities.append(ISYAuxSensorEntity(node, PROP_COMMS_ERROR, False))

    for vname, vobj in hass_isy_data[ISY994_VARIABLES]:
        entities.append(ISYSensorVariableEntity(vname, vobj))

    await migrate_old_unique_ids(hass, SENSOR, entities)
    async_add_entities(entities)


class ISYSensorEntity(ISYNodeEntity, SensorEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def target(self) -> Node | NodeProperty | None:
        """Return target for the sensor."""
        return self._node

    @property
    def target_value(self) -> Any:
        """Return the target value."""
        return self._node.status

    @property
    def raw_unit_of_measurement(self) -> dict | str | None:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        if self.target is None:
            return None

        uom = self.target.uom

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
        if self.target is None:
            return None

        if (value := self.target_value) == ISY_VALUE_UNKNOWN:
            return None

        # Get the translated ISY Unit of Measurement
        uom = self.raw_unit_of_measurement

        # Check if this is a known index pair UOM
        if isinstance(uom, dict):
            return uom.get(value, value)

        if uom in (UOM_INDEX, UOM_ON_OFF):
            return cast(str, self.target.formatted)

        # Check if this is an index type and get formatted value
        if uom == UOM_INDEX and hasattr(self.target, "formatted"):
            return cast(str, self.target.formatted)

        # Handle ISY precision and rounding
        value = convert_isy_value_to_hass(value, uom, self.target.prec)

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


class ISYAuxSensorEntity(ISYSensorEntity):
    """Representation of an ISY994 aux sensor device."""

    def __init__(self, node: Node, control: str, enabled_default: bool) -> None:
        """Initialize the ISY994 aux sensor."""
        super().__init__(node)
        self._control = control
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_entity_category = ISY_CONTROL_TO_ENTITY_CATEGORY.get(control)
        self._attr_device_class = ISY_CONTROL_TO_DEVICE_CLASS.get(control)
        self._attr_state_class = ISY_CONTROL_TO_STATE_CLASS.get(control)

    @property
    def target(self) -> Node | NodeProperty | None:
        """Return target for the sensor."""
        if self._control not in self._node.aux_properties:
            # Property not yet set (i.e. no errors)
            return None
        return cast(NodeProperty, self._node.aux_properties[self._control])

    @property
    def target_value(self) -> Any:
        """Return the target value."""
        return None if self.target is None else self.target.value

    @property
    def unique_id(self) -> str | None:
        """Get the unique identifier of the device and aux sensor."""
        if not hasattr(self._node, "address"):
            return None
        return f"{self._node.isy.configuration['uuid']}_{self._node.address}_{self._control}"

    @property
    def name(self) -> str:
        """Get the name of the device and aux sensor."""
        base_name = self._name or str(self._node.name)
        name = COMMAND_FRIENDLY_NAME.get(self._control, self._control)
        return f"{base_name} {name.replace('_', ' ').title()}"


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
