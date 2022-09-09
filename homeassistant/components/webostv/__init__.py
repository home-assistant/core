"""Support for LG webOS Smart TV."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextlib import suppress
import logging
from typing import Any

from aiowebostv import WebOsClient, WebOsTvPairError
import voluptuous as vol

from homeassistant.components import notify as hass_notify
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    Context,
    Event,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.trigger import TriggerActionType
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BUTTON,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    DATA_CONFIG_ENTRY,
    DATA_HASS_CONFIG,
    DOMAIN,
    PLATFORMS,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WEBOSTV_EXCEPTIONS,
)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

BUTTON_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_BUTTON): cv.string})

COMMAND_SCHEMA = CALL_SCHEMA.extend(
    {vol.Required(ATTR_COMMAND): cv.string, vol.Optional(ATTR_PAYLOAD): dict}
)

SOUND_OUTPUT_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_SOUND_OUTPUT): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_BUTTON: {"method": "async_button", "schema": BUTTON_SCHEMA},
    SERVICE_COMMAND: {"method": "async_command", "schema": COMMAND_SCHEMA},
    SERVICE_SELECT_SOUND_OUTPUT: {
        "method": "async_select_sound_output",
        "schema": SOUND_OUTPUT_SCHEMA,
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LG WebOS TV platform."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    wrapper = WebOsClientWrapper(host, client_key=key)
    await wrapper.connect()

    async def async_service_handler(service: ServiceCall) -> None:
        method = SERVICE_TO_METHOD[service.service]
        data = service.data.copy()
        data["method"] = method["method"]
        async_dispatcher_send(hass, DOMAIN, data)

    for service, method in SERVICE_TO_METHOD.items():
        schema = method["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = wrapper
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            "notify",
            DOMAIN,
            {
                CONF_NAME: entry.title,
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            },
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    if not entry.update_listeners:
        entry.async_on_unload(entry.add_update_listener(async_update_options))

    async def async_on_stop(_event: Event) -> None:
        """Unregister callbacks and disconnect."""
        await wrapper.shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)
    )
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_control_connect(host: str, key: str | None) -> WebOsClient:
    """LG Connection."""
    client = WebOsClient(host, key)
    try:
        await client.connect()
    except WebOsTvPairError:
        _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
        raise

    return client


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        client = hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)
        await hass_notify.async_reload(hass, DOMAIN)
        await client.shutdown()

    # unregister service calls, check if this is the last entry to unload
    if unload_ok and not hass.data[DOMAIN][DATA_CONFIG_ENTRY]:
        for service in SERVICE_TO_METHOD:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok


class PluggableAction:
    """A pluggable action handler."""

    def __init__(self) -> None:
        """Initialize."""
        self._actions: dict[
            Callable[[], None],
            tuple[HassJob[..., Coroutine[Any, Any, None]], dict[str, Any]],
        ] = {}

    def __bool__(self) -> bool:
        """Return if we have something attached."""
        return bool(self._actions)

    @callback
    def async_attach(
        self, action: TriggerActionType, variables: dict[str, Any]
    ) -> Callable[[], None]:
        """Attach a device trigger for turn on."""

        @callback
        def _remove() -> None:
            del self._actions[_remove]

        job = HassJob(action)

        self._actions[_remove] = (job, variables)

        return _remove

    @callback
    def async_run(self, hass: HomeAssistant, context: Context | None = None) -> None:
        """Run all turn on triggers."""
        for job, variables in self._actions.values():
            hass.async_run_hass_job(job, variables, context)


class WebOsClientWrapper:
    """Wrapper for a WebOS TV client with Home Assistant specific functions."""

    def __init__(self, host: str, client_key: str) -> None:
        """Set up the client."""
        self.host = host
        self.client_key = client_key
        self.turn_on = PluggableAction()
        self.client: WebOsClient | None = None

    async def connect(self) -> None:
        """Attempt a connection, but fail gracefully if tv is off for example."""
        self.client = WebOsClient(self.host, self.client_key)
        with suppress(*WEBOSTV_EXCEPTIONS, WebOsTvPairError):
            await self.client.connect()

    async def shutdown(self) -> None:
        """Unregister callbacks and disconnect."""
        assert self.client
        self.client.clear_state_update_callbacks()
        await self.client.disconnect()
