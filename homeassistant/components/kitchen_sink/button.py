"""Demo platform that offers a fake button entity."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo button platform."""
    async_add_entities(
        [
            DemoButton(
                unique_id="2_ch_power_strip",
                device_name=None,
                device_translation_key="n_ch_power_strip",
                device_translation_placeholders={"number_of_sockets": "2"},
                entity_name="Restart",
            ),
        ]
    )


class DemoButton(ButtonEntity):
    """Representation of a demo button entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str | None,
        device_translation_key: str | None,
        device_translation_placeholders: dict[str, str] | None,
        entity_name: str | None,
    ) -> None:
        """Initialize the Demo button entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
            translation_key=device_translation_key,
            translation_placeholders=device_translation_placeholders,
        )
        self._attr_name = entity_name

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        persistent_notification.async_create(
            self.hass, "Button pressed", title="Button"
        )
        self.hass.bus.async_fire("demo_button_pressed")
