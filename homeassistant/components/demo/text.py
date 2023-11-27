"""Demo platform that offers a fake text entity."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo text platform."""
    async_add_entities(
        [
            DemoText(
                unique_id="text",
                device_name="Text",
                icon=None,
                native_value="Hello world",
            ),
            DemoText(
                unique_id="password",
                device_name="Password",
                icon="mdi:text",
                native_value="Hello world",
                mode=TextMode.PASSWORD,
            ),
            DemoText(
                unique_id="text_1_to_5_char",
                device_name="Text with 1 to 5 characters",
                icon="mdi:text",
                native_value="Hello",
                native_min=1,
                native_max=5,
            ),
            DemoText(
                unique_id="text_lowercase",
                device_name="Text with only lower case characters",
                icon="mdi:text",
                native_value="world",
                pattern=r"[a-z]+",
            ),
        ]
    )


class DemoText(TextEntity):
    """Representation of a demo text entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        icon: str | None,
        native_value: str | None,
        mode: TextMode = TextMode.TEXT,
        native_max: int | None = None,
        native_min: int | None = None,
        pattern: str | None = None,
    ) -> None:
        """Initialize the Demo text entity."""
        self._attr_unique_id = unique_id
        self._attr_native_value = native_value
        self._attr_icon = icon
        self._attr_mode = mode
        if native_max is not None:
            self._attr_native_max = native_max
        if native_min is not None:
            self._attr_native_min = native_min
        if pattern is not None:
            self._attr_pattern = pattern
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )

    async def async_set_value(self, value: str) -> None:
        """Update the value."""
        self._attr_native_value = value
        self.async_write_ha_state()
