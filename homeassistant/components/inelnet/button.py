"""Button platform for INELNET Blinds. One device per channel; each button controls only that channel."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InelnetConfigEntry
from .const import (
    ACT_DOWN_SHORT,
    ACT_PROGRAM,
    ACT_UP_SHORT,
    DEVICE_NAME_CHANNEL_TEMPLATE,
    DOMAIN,
)
from .cover import send_command

# Button kinds: (unique_id_suffix, action_code) – name from entity translation key
BUTTON_UP_SHORT = ("short_up", ACT_UP_SHORT)
BUTTON_DOWN_SHORT = ("short_down", ACT_DOWN_SHORT)
BUTTON_PROGRAM = ("program", ACT_PROGRAM)


def _device_info(entry: ConfigEntry, channel: int) -> DeviceInfo:
    """Build DeviceInfo for a channel (same as cover so entities share one device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}-ch{channel}")},
        name=DEVICE_NAME_CHANNEL_TEMPLATE.format(channel=channel),
        manufacturer="INELNET",
        model="Blinds controller",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up three buttons per channel. Each channel is one device; each button acts on that channel only."""
    data = entry.runtime_data
    host = data.host
    channels = data.channels

    entities: list[InelnetButtonEntity] = []
    for channel in channels:
        for translation_key, act_code in (
            BUTTON_UP_SHORT,
            BUTTON_DOWN_SHORT,
            BUTTON_PROGRAM,
        ):
            entities.append(
                InelnetButtonEntity(
                    entry=entry,
                    host=host,
                    channel=channel,
                    unique_id_suffix=translation_key,
                    action_code=act_code,
                    translation_key=translation_key,
                )
            )
    async_add_entities(entities)


class InelnetButtonEntity(ButtonEntity):
    """One button entity for a single INELNET action (short up, short down, program)."""

    _attr_has_entity_name = True
    # Disabled by default so the user must enable these entities explicitly
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entry: ConfigEntry,
        host: str,
        channel: int,
        unique_id_suffix: str,
        action_code: int,
        translation_key: str,
    ) -> None:
        """Initialize the button."""
        self._entry = entry
        self._host = host
        self._channel = channel
        self._action_code = action_code
        self._attr_unique_id = f"{entry.entry_id}-ch{channel}-{unique_id_suffix}"
        self._attr_translation_key = translation_key
        self._attr_device_info = _device_info(entry, channel)

    async def async_press(self) -> None:
        """Send the REST command for this action."""
        await send_command(self.hass, self._host, self._channel, self._action_code)
