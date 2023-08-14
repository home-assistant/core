"""public IP address Sensor."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, TRACKER_UPDATE_STR
from .coordinator import NoIPDataUpdateCoordinator


class NoIPBaseEntity(CoordinatorEntity[NoIPDataUpdateCoordinator], RestoreSensor):
    """Base entity class for No-IP.com."""

    _attr_force_update = False

    def __init__(self, coordinator: NoIPDataUpdateCoordinator) -> None:
        """Init base entity class."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(MANUFACTURER, f"{self.coordinator.data[CONF_DOMAIN]}")},
            manufacturer=MANUFACTURER,
            name=f"{self.coordinator.data[CONF_DOMAIN]}",
            configuration_url="https://www.home-assistant.io/integrations/no_ip",
        )
        self._unsub_dispatchers: list[Callable[[], None]] = []

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        if self.coordinator.data:
            self._attr_native_value = self.coordinator.data.get(CONF_IP_ADDRESS, None)
        self._unsub_dispatchers.append(
            async_dispatcher_connect(
                self.hass, TRACKER_UPDATE_STR, self.async_write_ha_state
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up before removing the entity."""
        for unsub in self._unsub_dispatchers[:]:
            unsub()
            self._unsub_dispatchers.remove(unsub)
        self._unsub_dispatchers = []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the No-IP.com sensors from config entry."""
    coordinator: NoIPDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[NoIPSensor] = []
    if CONF_DOMAIN in coordinator.data:
        entities.append(NoIPSensor(coordinator))
    async_add_entities(entities)


class NoIPSensor(NoIPBaseEntity, SensorEntity):
    """NoIPSensor class for No-IP.com."""

    _attr_icon = "mdi:ip"

    def __init__(self, coordinator: NoIPDataUpdateCoordinator) -> None:
        """Init NoIPSensor."""
        super().__init__(coordinator)
        self._attr_name: str = f"{coordinator.data[CONF_DOMAIN]}"
        self._attr_unique_id = f"{coordinator.data[CONF_DOMAIN]}"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if CONF_IP_ADDRESS in self.coordinator.data:
            return str(self.coordinator.data[CONF_IP_ADDRESS])
        return None
