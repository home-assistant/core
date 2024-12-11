"""The Niko home control integration."""

from __future__ import annotations

from typing import Any

from nclib.errors import NetcatError
from nhc.controller import NHCController as _NHCController

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [Platform.LIGHT]

type NikoHomeControlConfigEntry = ConfigEntry[NHCController]


async def event_handler(self, event) -> None:
    """Handle events."""
    entity = self.get_entity(event["id"])
    entity.update_state(event["value1"])


async def async_setup_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Set Niko Home Control from a config entry."""
    try:
        controller = NHCController(entry.data[CONF_HOST], 8000)
        await controller.connect()
        entry.runtime_data = controller
        controller.add_callback(event_handler)
    except NetcatError as err:
        raise ConfigEntryNotReady("cannot connect to controller.") from err
    except OSError as err:
        raise ConfigEntryNotReady(
            "unknown error while connecting to controller."
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class NHCController(_NHCController):
    """The niko home control controller."""

    def __init__(self, host, port) -> None:
        """Init niko home control controller."""
        super().__init__(host, port)
        self.entities: dict[str, Any] = {}

    def get_entity(self, action_id):
        """Get entity by id."""
        return self.entities[action_id]
