"""Demo platform that offers a fake button entity."""

from dataclasses import dataclass
from typing import override

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class DemoButtonEntityDescription(ButtonEntityDescription):
    """Describes a demo button."""

    device_name: str | None
    device_translation_key: str | None
    device_translation_placeholders: dict[str, str] | None


BUTTONS = (
    DemoButtonEntityDescription(
        key="2_ch_power_strip",
        name="Restart",
        device_name=None,
        device_translation_key="n_ch_power_strip",
        device_translation_placeholders={"number_of_sockets": "2"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo button platform."""
    async_add_entities(DemoButton(description) for description in BUTTONS)


class DemoButton(ButtonEntity):
    """Representation of a demo button entity."""

    entity_description: DemoButtonEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, description: DemoButtonEntityDescription) -> None:
        """Initialize the Demo button entity."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, description.key)},
            name=description.device_name,
            translation_key=description.device_translation_key,
            translation_placeholders=description.device_translation_placeholders,
        )

    @override
    async def async_press(self) -> None:
        """Send out a persistent notification."""
        persistent_notification.async_create(
            self.hass, "Button pressed", title="Button"
        )
        self.hass.bus.async_fire("demo_button_pressed")
