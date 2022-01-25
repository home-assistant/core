"""Support for LG webOS Smart TV."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import json
import logging
import os
from pickle import loads
from typing import Any

from aiowebostv import WebOsClient, WebOsTvPairError
import sqlalchemy as db
import voluptuous as vol

from homeassistant.components import notify as hass_notify
from homeassistant.components.automation import AutomationActionType
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_CLIENT_SECRET,
    CONF_CUSTOMIZE,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import (
    Context,
    Event,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv, discovery, entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BUTTON,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_ON_ACTION,
    CONF_SOURCES,
    DATA_CONFIG_ENTRY,
    DATA_HASS_CONFIG,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WEBOSTV_CONFIG_FILE,
    WEBOSTV_EXCEPTIONS,
)

CUSTOMIZE_SCHEMA = vol.Schema(
    {vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [cv.string])}
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA,
                            vol.Required(CONF_HOST): cv.string,
                            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                            vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                            vol.Optional(CONF_ICON): cv.string,
                        }
                    )
                ],
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

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


def read_client_keys(config_file: str) -> dict[str, str]:
    """Read legacy client keys from file."""
    if not os.path.isfile(config_file):
        return {}

    # Try to parse the file as being JSON
    with open(config_file, encoding="utf8") as json_file:
        try:
            client_keys = json.load(json_file)
            if isinstance(client_keys, dict):
                return client_keys
            return {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # If the file is not JSON, read it as Sqlite DB
    engine = db.create_engine(f"sqlite:///{config_file}")
    table = db.Table("unnamed", db.MetaData(), autoload=True, autoload_with=engine)
    results = engine.connect().execute(db.select([table])).fetchall()
    db_client_keys = {k: loads(v) for k, v in results}
    return db_client_keys


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LG WebOS TV platform."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    if DOMAIN not in config:
        return True

    config_file = hass.config.path(WEBOSTV_CONFIG_FILE)
    if not (
        client_keys := await hass.async_add_executor_job(read_client_keys, config_file)
    ):
        _LOGGER.debug("No pairing keys, Not importing webOS Smart TV YAML config")
        return True

    async def async_migrate_task(
        entity_id: str, conf: dict[str, str], key: str
    ) -> None:
        _LOGGER.debug("Migrating webOS Smart TV entity %s unique_id", entity_id)
        client = WebOsClient(conf[CONF_HOST], key)
        tries = 0
        while not client.is_connected():
            try:
                await client.connect()
            except WEBOSTV_EXCEPTIONS:
                if tries == 0:
                    _LOGGER.warning(
                        "Please make sure webOS TV %s is turned on to complete "
                        "the migration of configuration.yaml to the UI",
                        entity_id,
                    )
                wait_time = 2 ** min(tries, 4) * 5
                tries += 1
                await asyncio.sleep(wait_time)
            except WebOsTvPairError:
                return

        ent_reg = entity_registry.async_get(hass)
        if not (
            new_entity_id := ent_reg.async_get_entity_id(
                Platform.MEDIA_PLAYER, DOMAIN, key
            )
        ):
            _LOGGER.debug(
                "Not updating webOSTV Smart TV entity %s unique_id, entity missing",
                entity_id,
            )
            return

        uuid = client.hello_info["deviceUUID"]
        ent_reg.async_update_entity(new_entity_id, new_unique_id=uuid)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                **conf,
                CONF_CLIENT_SECRET: key,
                CONF_UNIQUE_ID: uuid,
            },
        )

    ent_reg = entity_registry.async_get(hass)

    tasks = []
    for conf in config[DOMAIN]:
        host = conf[CONF_HOST]
        if (key := client_keys.get(host)) is None:
            _LOGGER.debug(
                "Not importing webOS Smart TV host %s without pairing key", host
            )
            continue

        if entity_id := ent_reg.async_get_entity_id(Platform.MEDIA_PLAYER, DOMAIN, key):
            tasks.append(asyncio.create_task(async_migrate_task(entity_id, conf, key)))

    async def async_tasks_cancel(_event: Event) -> None:
        """Cancel config flow import tasks."""
        for task in tasks:
            if not task.done():
                task.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_tasks_cancel)

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
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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
        self._actions: dict[Callable[[], None], tuple[HassJob, dict[str, Any]]] = {}

    def __bool__(self) -> bool:
        """Return if we have something attached."""
        return bool(self._actions)

    @callback
    def async_attach(
        self, action: AutomationActionType, variables: dict[str, Any]
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
