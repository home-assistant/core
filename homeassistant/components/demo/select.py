"""Demo platform that offers a fake select entity."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    """Set up the demo select platform."""
    async_add_entities(
        [
            DemoSelect(
                unique_id="speed",
                device_name="Speed",
                icon="mdi:speedometer",
                current_option="ridiculous_speed",
                options=[
                    "light_speed",
                    "ridiculous_speed",
                    "ludicrous_speed",
                ],
                translation_key="speed",
            ),
        ]
    )


class DemoSelect(SelectEntity):
    """Representation of a demo select entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        icon: str,
        current_option: str | None,
        options: list[str],
        translation_key: str,
    ) -> None:
        """Initialize the Demo select entity."""
        self._attr_unique_id = unique_id
        self._attr_current_option = current_option
        self._attr_icon = icon
        self._attr_options = options
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()
