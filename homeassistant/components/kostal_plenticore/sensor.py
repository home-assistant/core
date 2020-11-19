"""Platform for Kostal Plenticore sensors."""
import logging
from typing import Any, Callable, Dict, Optional, Union

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ENABLED_DEFAULT,
    ATTR_VALUE,
    DOMAIN,
    SCOPE_PROCESS_DATA,
    SCOPE_SETTING,
    SENSOR_PROCESS_DATA,
    SENSOR_SETTINGS_DATA,
    SERVICE_SET_VALUE,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VALUE): vol.Coerce(str),
    }
)


def format_round(state: str) -> Union[int, str]:
    """Return the given state value as rounded integer."""
    try:
        return round(float(state))
    except (TypeError, ValueError):
        return state


def format_energy(state: str) -> Union[float, str]:
    """Return the given state value as energy value, scaled to kWh."""
    try:
        return round(float(state) / 1000, 1)
    except (TypeError, ValueError):
        return state


def format_inverter_state(state: str) -> str:
    """Return a readable string of the inverter state."""
    try:
        value = int(state)
    except (TypeError, ValueError):
        return state

    if value == 0:
        return "Off"
    if value == 1:
        return "Init"
    if value == 2:
        return "IsoMEas"
    if value == 3:
        return "GridCheck"
    if value == 4:
        return "StartUp"
    if value == 6:
        return "FeedIn"
    if value == 7:
        return "Throttled"
    if value == 8:
        return "ExtSwitchOff"
    if value == 9:
        return "Update"
    if value == 10:
        return "Standby"
    if value == 11:
        return "GridSync"
    if value == 12:
        return "GridPreCheck"
    if value == 13:
        return "GridSwitchOff"
    if value == 14:
        return "Overheating"
    if value == 15:
        return "Shutdown"
    if value == 16:
        return "ImproperDcVoltage"
    if value == 17:
        return "ESB"
    return "Unknown"


def format_em_manager_state(state: str) -> str:
    """Return a readable state of the energy manager."""
    try:
        value = int(state)
    except (TypeError, ValueError):
        return state

    if value == 0:
        return "Idle"
    if value == 1:
        return "n/a"
    if value == 2:
        return "Emergency Battery Charge"
    if value == 4:
        return "n/a"
    if value == 8:
        return "Winter Mode Step 1"
    if value == 16:
        return "Winter Mode Step 2"

    return "Unknown"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Add kostal plenticore Sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for module_id, data_id, name, sensor_data, fmt in SENSOR_PROCESS_DATA:
        # get function for string
        fmt = globals()[str(fmt)]

        entities.append(
            PlenticoreProcessDataSensor(
                coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                data_id,
                name,
                sensor_data,
                fmt,
            )
        )

    for module_id, data_id, name, sensor_data, fmt in SENSOR_SETTINGS_DATA:
        # get function for string
        fmt = globals()[str(fmt)]

        entities.append(
            PlenticoreSettingSensor(
                coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                data_id,
                name,
                sensor_data,
                fmt,
            )
        )

    async_add_entities(entities)

    # await coordinator.async_refresh()

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_VALUE,
        SERVICE_SET_VALUE_SCHEMA,
        "async_set_new_value",
    )

    return True


class PlenticoreProcessDataSensor(CoordinatorEntity):
    """Representation of a Plenticore process data Sensor."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        module_id: str,
        data_id: str,
        sensor_name: str,
        sensor_data: Dict[str, Any],
        formatter: Callable[[str], Any],
    ):
        """Create a new Sensor Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self.data_id = data_id

        self._sensor_name = sensor_name
        self._sensor_data = sensor_data
        self._formatter = formatter

        self._available = True

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        self.coordinator.register_entity(self)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        await super().async_will_remove_from_hass()
        self.coordinator.unregister_entity(self)

    @property
    def available(self) -> bool:
        """Return if this entity can be access in the current Plenticore firmware version."""
        return self._available

    @available.setter
    def available(self, available) -> None:
        """Set the availability of this entity."""
        self._available = available

    @property
    def scope(self) -> str:
        """Return the scope of this Sensor Entity."""
        return SCOPE_PROCESS_DATA

    @property
    def unique_id(self) -> str:
        """Return the unique id of this Sensor Entity."""
        return f"{self.entry_id}_{self._sensor_name}"

    @property
    def name(self) -> str:
        """Return the name of this Sensor Entity."""
        return f"{self.platform_name} {self._sensor_name}"

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_UNIT_OF_MEASUREMENT, None)

    @property
    def icon(self) -> Optional[str]:
        """Return the icon name of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_ICON, None)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._sensor_data.get(ATTR_DEVICE_CLASS, None)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._sensor_data.get(ATTR_ENABLED_DEFAULT, False)

    @property
    def state(self) -> Optional[Any]:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            # None is translated to STATE_UNKNOWN
            return None

        try:
            raw_value = self.coordinator.data[self.scope][self.module_id][self.data_id]
        except KeyError:
            return STATE_UNAVAILABLE

        return self._formatter(raw_value) if self._formatter else raw_value

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Device info."""
        return self.coordinator.device_info


class PlenticoreSettingSensor(PlenticoreProcessDataSensor):
    """Representation of a Plenticore setting value Sensor."""

    @property
    def scope(self) -> str:
        """Return the scope of this Sensor Entity."""
        return SCOPE_SETTING

    async def async_set_new_value(self, value) -> None:
        """Write the given value to the setting of this entity instance."""
        await self.coordinator.async_write_setting(
            self.module_id, self.data_id, str(value)
        )
