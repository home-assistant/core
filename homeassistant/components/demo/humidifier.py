"""Demo platform that offers a fake humidifier device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SUPPORT_FLAGS = HumidifierEntityFeature(0)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo humidifier devices."""
    async_add_entities(
        [
            DemoHumidifier(
                name="Humidifier",
                mode=None,
                target_humidity=68,
                current_humidity=45,
                action=HumidifierAction.HUMIDIFYING,
                device_class=HumidifierDeviceClass.HUMIDIFIER,
            ),
            DemoHumidifier(
                name="Dehumidifier",
                mode=None,
                target_humidity=54,
                current_humidity=59,
                action=HumidifierAction.DRYING,
                device_class=HumidifierDeviceClass.DEHUMIDIFIER,
            ),
            DemoHumidifier(
                name="Hygrostat",
                mode="home",
                available_modes=["home", "eco"],
                target_humidity=50,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo humidifier devices config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoHumidifier(HumidifierEntity):
    """Representation of a demo humidifier device."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        mode: str | None,
        target_humidity: int,
        current_humidity: int | None = None,
        available_modes: list[str] | None = None,
        is_on: bool = True,
        action: HumidifierAction | None = None,
        device_class: HumidifierDeviceClass | None = None,
    ) -> None:
        """Initialize the humidifier device."""
        self._attr_name = name
        self._attr_is_on = is_on
        self._attr_action = action
        self._attr_supported_features = SUPPORT_FLAGS
        if mode is not None:
            self._attr_supported_features |= HumidifierEntityFeature.MODES
        self._attr_target_humidity = target_humidity
        self._attr_current_humidity = current_humidity
        self._attr_mode = mode
        self._attr_available_modes = available_modes
        self._attr_device_class = device_class

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new humidity level."""
        self._attr_target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Update mode."""
        self._attr_mode = mode
        self.async_write_ha_state()
