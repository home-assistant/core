"""Support for Speedtest.net internet speed testing button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.speedtestdotnet import SpeedTestDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import ATTRIBUTION, DEFAULT_NAME, DOMAIN, SPEED_TEST_SERVICE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Speedtestdotnet buttons."""
    speedtest_coordinator = hass.data[DOMAIN]
    async_add_entities([SpeedtestButton(speedtest_coordinator)])


class SpeedtestButton(CoordinatorEntity, ButtonEntity):
    """Implementation of a speedtest.net button."""

    coordinator: SpeedTestDataCoordinator
    _attr_icon = "mdi:play-speed"
    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(
        self,
        coordinator: SpeedTestDataCoordinator,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_name = f"{DEFAULT_NAME} run now"
        self._attr_unique_id = slugify(self._attr_name)
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type="service",
            configuration_url="https://www.speedtest.net/",
        )

    async def async_press(self) -> None:
        """Immediately execute a speed test with Speedtest.net."""
        await self.hass.services.async_call(DOMAIN, SPEED_TEST_SERVICE)
