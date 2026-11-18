"""The Code Mode integration."""

from contextlib import AsyncExitStack

from pydantic_monty import AsyncMonty, MontyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import llm

from .api import CodeModeAPI

type CodeModeConfigEntry = ConfigEntry[AsyncMonty]

MAX_WORKERS = 4
CHECKOUT_TIMEOUT = 10


async def async_setup_entry(hass: HomeAssistant, entry: CodeModeConfigEntry) -> None:
    """Start the sandbox worker pool."""
    stack = AsyncExitStack()
    try:
        entry.runtime_data = await stack.enter_async_context(
            AsyncMonty(max_processes=MAX_WORKERS, checkout_timeout=CHECKOUT_TIMEOUT)
        )
    except (MontyError, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot start the sandbox: {err}") from err
    entry.async_on_unload(stack.aclose)
    entry.async_on_unload(
        llm.async_register_api(hass, CodeModeAPI(hass, entry.runtime_data))
    )


async def async_unload_entry(hass: HomeAssistant, entry: CodeModeConfigEntry) -> None:
    """Unload a config entry."""
