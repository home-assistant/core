"""Support for Fast.com internet speed testing sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_UPDATED as FASTDOTCOM_DOMAIN, DOMAIN
from .coordinator import FastdotcomDataUpdateCoordindator

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fast.com sensor."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{FASTDOTCOM_DOMAIN}",
        breaks_in_ha_version="2024.2.0",
        is_fixable=False,
        issue_domain=FASTDOTCOM_DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": FASTDOTCOM_DOMAIN,
            "integration_title": "Fast.com",
        },
    )
    async_add_entities([SpeedtestSensor(hass.data[FASTDOTCOM_DOMAIN])])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fast.com sensor."""
    coordinator: FastdotcomDataUpdateCoordindator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SpeedtestSensor(coordinator)], True)


class SpeedtestSensor(
    CoordinatorEntity[FastdotcomDataUpdateCoordindator], SensorEntity
):
    """Implementation of a Fast.com sensor."""

    _attr_name = "Fast.com Download"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: FastdotcomDataUpdateCoordindator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}"

    @property
    # Disabling the pylint, since it's an old function of fastdotcom that's being used
    # which isn't giving a proper type back
    # pylint: disable=hass-return-type
    def native_value(
        self,
    ) -> StateType | str | Any | None:
        """Return the state of the sensor."""
        return self.coordinator.data
