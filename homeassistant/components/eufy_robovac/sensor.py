"""Sensor platform for Eufy RoboVac."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_MODEL, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EufyRoboVacConfigEntry,
    RoboVacCommand,
    dps_update_signal,
)
from .model_mappings import MODEL_MAPPINGS, RoboVacModelMapping

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyRoboVacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eufy RoboVac sensors from a config entry."""
    model_code: str = entry.data[CONF_MODEL]
    mapping = MODEL_MAPPINGS[model_code]

    async_add_entities([EufyRoboVacBatterySensor(entry=entry, mapping=mapping)])


class EufyRoboVacBatterySensor(SensorEntity):
    """Battery sensor for a Eufy RoboVac."""

    _attr_has_entity_name = True
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(
        self, *, entry: EufyRoboVacConfigEntry, mapping: RoboVacModelMapping
    ) -> None:
        """Initialize battery sensor."""
        self._entry = entry
        self._battery_dps_code = str(mapping.commands[RoboVacCommand.BATTERY])
        self._attr_unique_id = f"{entry.data[CONF_ID]}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data[CONF_ID]))},
            manufacturer="Eufy",
            model=mapping.display_name,
            name=entry.data[CONF_NAME],
        )

    @callback
    def _async_update_from_dps(self, dps: dict[str, Any], *, write_state: bool) -> None:
        """Update sensor state from a DPS payload."""
        battery_raw = dps.get(self._battery_dps_code)
        if battery_raw is None:
            return

        try:
            self._attr_native_value = int(float(str(battery_raw)))
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Could not parse battery for %s: %s",
                self._entry.data[CONF_ID],
                battery_raw,
            )
            return

        if write_state:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to DPS updates from vacuum entity."""

        @callback
        def _handle_dps_update(dps: dict[str, Any]) -> None:
            self._async_update_from_dps(dps, write_state=True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dps_update_signal(self._entry.entry_id),
                _handle_dps_update,
            )
        )

        dps = self._entry.runtime_data.get("dps")
        if isinstance(dps, dict):
            self._async_update_from_dps(dps, write_state=False)
