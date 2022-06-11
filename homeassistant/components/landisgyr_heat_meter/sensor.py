"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import asdict, fields
import logging

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _entity_category(attribute_name) -> EntityCategory | None:
    if attribute_name in [
        "heat_usage_gj",
        "volume_usage_m3",
        "volume_previous_year_m3",
        "heat_previous_year_gj",
    ]:
        return None
    return EntityCategory.DIAGNOSTIC


def _state_class(attribute_name) -> SensorStateClass | None:
    if attribute_name in [
        "heat_usage_gj",
        "volume_usage_m3",
        "volume_previous_year_m3",
        "heat_previous_year_gj",
        "flow_hours",
        "operating_hours",
    ]:
        return SensorStateClass.TOTAL_INCREASING
    return None


def _icon(attribute_name) -> str | None:
    if "heat" in attribute_name or "volume" in attribute_name:
        return "mdi:fire"
    if "temperature" in attribute_name:
        return "mdi:thermometer"
    if "power" in attribute_name:
        return "mdi:power-plug-outline"
    if "m3ph" in attribute_name:
        return "mdi:water-outline"
    if any(tag in attribute_name for tag in ("day", "hours", "time")):
        return "mdi:clock-outline"
    if "measurement" in attribute_name:
        return "mdi:timer-outline"
    if "error" in attribute_name:
        return "mdi:home-alert"
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    _LOGGER.info("The Landis+Gyr Heat Meter sensor platform is being set up!")

    unique_id = entry.entry_id
    api = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from the API."""
        return await hass.async_add_executor_job(api.read)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="ultraheat_gateway",
        update_method=async_update_data,
        update_interval=None,
    )

    await coordinator.async_config_entry_first_refresh()

    model = entry.data["model"]

    device = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Landis & Gyr",
        model=model,
        name="Landis+Gyr Heat Meter",
    )

    async_add_entities(
        HeatMeterSensor(coordinator, field.name, device)
        for field in fields(coordinator.data)
    )


class HeatMeterSensor(CoordinatorEntity, RestoreSensor):
    """Representation of a Sensor."""

    def __init__(self, coordinator, idx, device):
        """Set up the sensor with the initial values."""
        super().__init__(coordinator)
        self._attr_should_poll = False
        self._attr_name = "Heat Meter " + idx.replace("_", " ")
        self._attr_icon = _icon(idx)
        self._attr_entity_category = _entity_category(idx)
        self._attr_state_class = _state_class(idx)
        self.idx = idx
        if "unit" in asdict(self.coordinator.data)[self.idx]:
            self._attr_native_unit_of_measurement = asdict(self.coordinator.data)[
                self.idx
            ]["unit"]
        self._attr_unique_id = f'{DOMAIN}_{device["model"]}_{idx}'
        self._attr_device_info = device

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # not yet implemented in package:
        self._attr_native_value = asdict(self.coordinator.data)[self.idx]["value"]
        self.async_write_ha_state()
