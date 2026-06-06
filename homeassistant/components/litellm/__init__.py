"""The LiteLLM integration."""

import litellm

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import PLACEHOLDER_API_KEY
from .coordinator import LiteLLMConfigEntry, LiteLLMDataUpdateCoordinator

PLATFORMS = [Platform.CONVERSATION]

# litellm collects anonymous telemetry and prints debug banners by default;
# disable both for Home Assistant.
litellm.telemetry = False
litellm.suppress_debug_info = True


def _warm_up_litellm() -> None:
    """Trigger litellm's lazy provider imports off the event loop.

    litellm imports provider and config modules lazily on first use, which
    would otherwise run blocking imports inside the event loop. A mock
    completion exercises the full request, response, and cost-tracking path
    without any network call, caching those imports up front.
    """
    litellm.completion(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "warmup"}],
        mock_response="warmup",
        # api_base is required to exercise the proxy request path; mock_response
        # short-circuits before any network call is made.
        api_base="http://localhost",
        api_key=PLACEHOLDER_API_KEY,
    )


async def async_setup_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> bool:
    """Set up LiteLLM from a config entry."""
    with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
        await hass.async_add_import_executor_job(_warm_up_litellm)

    coordinator = LiteLLMDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LiteLLMConfigEntry
) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> bool:
    """Unload LiteLLM."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
