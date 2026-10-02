"""The Mistral AI integration."""

from contextlib import suppress
import importlib
from typing import Any

from mistralai.client import Mistral, errors, utils
import mistralai.client.models as models_mod

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, LOGGER

__all__ = ["DOMAIN", "MistralAIConfigEntry"]

PLATFORMS = (Platform.CONVERSATION,)

type MistralAIConfigEntry = ConfigEntry[Mistral]


def _setup_client(api_key: str, async_client) -> Mistral:
    """Create the client, preload lazy SDK modules and validate the API key.

    Runs synchronously in the executor so that the Mistral SDK's lazy
    ``import_module`` calls never block the Home Assistant event loop.
    """
    client = Mistral(api_key=api_key, async_client=async_client)
    _preload_mistral_sdk()

    # Force the lazy sub-SDKs (chat/models) to load now, in the executor.
    _ = client.chat
    _ = client.models

    client.models.list(timeout_ms=10_000)
    return client


def _preload_mistral_sdk() -> None:
    """Import and materialize every lazily-imported Mistral SDK symbol up front.

    The Speakeasy-generated SDK resolves many names via module-level
    ``__getattr__`` hooks, which call ``import_module`` on *every* access (not
    just the first). That trips Home Assistant's "blocking call" detector when
    it happens inside the event loop. We run this in the executor and
    materialize each lazy attribute onto its module so ``__getattr__`` is never
    invoked again at call time.
    """
    for package in (utils, errors, models_mod):
        imports = getattr(package, "_dynamic_imports", {})

        modules: dict[str, Any] = {}
        for module_path in set(imports.values()):
            with suppress(ImportError):
                modules[module_path] = importlib.import_module(
                    module_path, package=package.__package__
                )

        for attr_name, module_path in imports.items():
            module = modules.get(module_path)
            if module is None:
                continue
            with suppress(AttributeError):
                setattr(package, attr_name, getattr(module, attr_name))


async def async_setup_entry(hass: HomeAssistant, entry: MistralAIConfigEntry) -> bool:
    """Set up Mistral AI from a config entry."""
    try:
        client = await hass.async_add_executor_job(
            _setup_client,
            entry.data[CONF_API_KEY],
            get_async_client(hass),
        )
    except Exception as err:  # mistralai raises SDKError with status_code
        status_code = getattr(err, "status_code", None)
        if status_code in (401, 403):
            raise ConfigEntryAuthFailed(err) from err
        LOGGER.error("Error talking to Mistral API: %s", err)
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: MistralAIConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
