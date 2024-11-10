"""Platform for eQ-3 binary sensor entities."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_NAME_BATTERY,
    ENTITY_NAME_BUSY,
    ENTITY_NAME_CONNECTED,
    ENTITY_NAME_DST,
    ENTITY_NAME_WINDOW_OPEN,
)
from .entity import Eq3Entity
from .models import Eq3ConfigEntryData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    eq3_config_entry: Eq3ConfigEntryData = hass.data[DOMAIN][config_entry.entry_id]

    entities_to_add: list[Entity] = [
        BatterySensor(eq3_config_entry.eq3_config, eq3_config_entry.thermostat),
        WindowOpenSensor(eq3_config_entry.eq3_config, eq3_config_entry.thermostat),
        DSTSensor(eq3_config_entry.eq3_config, eq3_config_entry.thermostat),
        BusySensor(eq3_config_entry.eq3_config, eq3_config_entry.thermostat),
        ConnectedSensor(eq3_config_entry.eq3_config, eq3_config_entry.thermostat),
    ]

    async_add_entities(entities_to_add)


class BusySensor(Eq3Entity, BinarySensorEntity):
    """Binary sensor that reports if the thermostat connection is busy."""

    _attr_name = ENTITY_NAME_BUSY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return if the thermostat connection is busy."""

        is_busy: bool = self._thermostat.is_busy
        return is_busy

    @property
    def available(self) -> bool:
        """Return if the binary sensor is available."""

        return True


class ConnectedSensor(Eq3Entity, BinarySensorEntity):
    """Binary sensor that reports if the thermostat is connected."""

    _attr_name = ENTITY_NAME_CONNECTED
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return if the thermostat is connected."""

        is_connected: bool = self._thermostat.is_connected
        return is_connected

    @property
    def available(self) -> bool:
        """Return if the binary sensor is available."""

        return True


class BatterySensor(Eq3Entity, BinarySensorEntity):
    """Binary sensor that reports if the thermostat battery is low."""

    _attr_name = ENTITY_NAME_BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    @property
    def is_on(self) -> bool | None:
        """Return if the thermostat battery is low."""

        if self._thermostat.status is None:
            return None

        is_low_battery: bool = self._thermostat.status.is_low_battery
        return is_low_battery


class WindowOpenSensor(Eq3Entity, BinarySensorEntity):
    """Binary sensor that reports if the thermostat thinks a window is open."""

    _attr_name = ENTITY_NAME_WINDOW_OPEN
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    @property
    def is_on(self) -> bool | None:
        """Return if the thermostat thinks a window is open."""

        if self._thermostat.status is None:
            return None

        is_window_open: bool = self._thermostat.status.is_window_open
        return is_window_open


class DSTSensor(Eq3Entity, BinarySensorEntity):
    """Binary sensor that reports if the thermostat is in daylight savings time mode."""

    _attr_name = ENTITY_NAME_DST
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return if the thermostat is in daylight savings time mode."""

        if self._thermostat.status is None:
            return None

        is_dst: bool = self._thermostat.status.is_dst
        return is_dst
