"""The FlowSpeech integration."""

from flowspeech_sdk import (
    FlowSpeechAuthError,
    FlowSpeechClient,
    FlowSpeechConnectionError,
    FlowSpeechError,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_API_KEY
from .types import FlowSpeechConfigEntry

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(
    hass: HomeAssistant, entry: FlowSpeechConfigEntry
) -> bool:
    """Set up FlowSpeech from a config entry."""
    client = FlowSpeechClient(api_key=entry.data[CONF_API_KEY])

    try:
        await hass.async_add_executor_job(client.get_quota)
    except FlowSpeechAuthError as exc:
        raise ConfigEntryAuthFailed(f"Invalid FlowSpeech API key: {exc}") from exc
    except FlowSpeechConnectionError as exc:
        raise ConfigEntryNotReady(f"Cannot connect to FlowSpeech: {exc}") from exc
    except FlowSpeechError as exc:
        raise ConfigEntryNotReady(f"FlowSpeech setup failed: {exc}") from exc

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: FlowSpeechConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: FlowSpeechConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
