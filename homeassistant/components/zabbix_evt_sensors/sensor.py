"""Support for Zabbix sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONFIG_KEY, DOMAIN, PROBLEMS_KEY, SERVICES_KEY
from .coordinator import ZabbixUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the config entry for zabbix sensor."""
    _LOGGER.info("Instantiating DataUpdateCoordinator")
    coordinator = ZabbixUpdateCoordinator(
        hass,
        _LOGGER,
        hass.data[DOMAIN][entry.entry_id],
        name="Zabbix Data Coordinator",
        update_interval=entry.data[CONFIG_KEY][CONF_SCAN_INTERVAL],
    )
    await coordinator.async_config_entry_first_refresh()
    for zbx_svc in coordinator.data[SERVICES_KEY]:
        async_add_entities(
            [ZabbixServiceSensor(coordinator, zbx_svc, entry.data["prefix"])]
        )
    for zbx_prb in entry.data[PROBLEMS_KEY]:
        async_add_entities(
            [ZabbixProblemSensor(coordinator, zbx_prb, entry.data["prefix"])]
        )


class ZabbixSensor(CoordinatorEntity, SensorEntity):
    """Generich Zabbix Sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:alpha-z-box"
    _attr_name = None
    zabbix_sensor_type_name: str | None = None
    zabbix_sensor_type_key: str = ""

    def __init__(self, coordinator, zbx_evt, prefix) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = zbx_evt
        self._attr_native_value = None
        self._attr_unique_id = f"zbx_{coordinator.zbx.host}_{self._attr_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.zbx.host}_{self.zabbix_sensor_type_name}")
            },
            name=f"{prefix} {self.zabbix_sensor_type_name}",
            configuration_url=coordinator.zbx.url,
            manufacturer="Zabbix SIA",
            sw_version=coordinator.zbx.zapi.version.public,
        )
        self._attr_should_poll = True
        _LOGGER.info("Created Zabbix sensor entity zbx_%s", self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("Updating entity %s state", self.name)
        entity_values = self.coordinator.data[self.zabbix_sensor_type_key].get(
            self._attr_name, []
        )
        entity_display_values = [
            f"{e.host}: {e.name} ({e.severity})" for e in entity_values
        ]
        self._attr_extra_state_attributes = {"events": entity_display_values}
        states = [e.severity for e in entity_values]
        state = max(states) if states else -1
        self._attr_native_value = state
        self.async_write_ha_state()


class ZabbixServiceSensor(ZabbixSensor):
    """Zabbix Service Sensor."""

    zabbix_sensor_type_name = "Service"
    zabbix_sensor_type_key = SERVICES_KEY


class ZabbixProblemSensor(ZabbixSensor):
    """Zabbix Problem Sensor."""

    zabbix_sensor_type_name = "Problem"
    zabbix_sensor_type_key = PROBLEMS_KEY
