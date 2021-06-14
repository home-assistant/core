"""Demo platform that offers a fake humidifier device."""
from __future__ import annotations

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
)

SUPPORT_FLAGS = 0


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo humidifier devices."""
    async_add_entities(
        [
            DemoHumidifier(
                name="Humidifier",
                mode=None,
                target_humidity=68,
                device_class=DEVICE_CLASS_HUMIDIFIER,
            ),
            DemoHumidifier(
                name="Dehumidifier",
                mode=None,
                target_humidity=54,
                device_class=DEVICE_CLASS_DEHUMIDIFIER,
            ),
            DemoHumidifier(
                name="Hygrostat",
                mode="home",
                available_modes=["home", "eco"],
                target_humidity=50,
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
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
        available_modes: list[str] | None = None,
        is_on: bool = True,
        device_class: str | None = None,
    ) -> None:
        """Initialize the humidifier device."""
        self._attr_name = name
        self._attr_is_on = is_on
        self._attr_supported_features = SUPPORT_FLAGS
        if mode is not None:
            self._attr_supported_features = (
                self._attr_supported_features | SUPPORT_MODES
            )
        self._attr_target_humidity = target_humidity
        self._attr_mode = mode
        self._attr_available_modes = available_modes
        self._attr_device_class = device_class

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._attr_target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_mode(self, mode):
        """Update mode."""
        self._attr_mode = mode
        self.async_write_ha_state()
