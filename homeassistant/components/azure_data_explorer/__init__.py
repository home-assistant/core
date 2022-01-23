"""The Azure Data Explorer integration."""
# pylint: disable=no-member
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.azure_data_explorer.client import AzureDataExplorerClient
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_FILTER,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DATA_HUB,
    DEFAULT_MAX_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ADX_CLUSTER_INGEST_URI): cv.string,
                vol.Optional(CONF_ADX_DATABASE_NAME): cv.string,
                vol.Optional(CONF_ADX_TABLE_NAME): cv.string,
                vol.Optional(CONF_APP_REG_ID): cv.string,
                vol.Optional(CONF_APP_REG_SECRET): cv.string,
                vol.Optional(CONF_AUTHORITY_ID): cv.string,
                vol.Optional(CONF_SEND_INTERVAL): cv.positive_int,
                vol.Optional(CONF_MAX_DELAY): cv.positive_int,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate ADX component from yaml.

    Adds an empty filter to hass data.
    Tries to get a filter from yaml, if present set to hass data.
    If config is empty after getting the filter, return, otherwise emit
    deprecated warning and pass the rest to the config flow.
    """

    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})
    if DOMAIN not in yaml_config:
        return True
    hass.data[DOMAIN][DATA_FILTER] = yaml_config[DOMAIN].pop(CONF_FILTER)

    if not yaml_config[DOMAIN]:
        return True
    _LOGGER.warning(
        "Loading Azure Data Explorer completely via yaml config is deprecated; Only the \
        Filter can be set in yaml, the rest is done through a config flow and has \
        been imported, all other keys but filter can be deleted from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config[DOMAIN]
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do the setup based on the config entry and the filter from yaml."""
    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})

    adx = AzureDataExplorer(
        hass,
        entry,
        hass.data[DOMAIN][DATA_FILTER],
    )
    try:
        result = await hass.async_add_executor_job(lambda: adx.test_connection())
        if result is not None:
            raise ConfigEntryNotReady("Could not connect to Azure Data Exlorer")
    except Exception as err:
        _LOGGER.error(err)
    hass.data[DOMAIN][DATA_HUB] = adx
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await adx.async_start()
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    hass.data[DOMAIN][DATA_HUB].update_options(entry.options)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    adx = hass.data[DOMAIN].pop(DATA_HUB)
    await adx.async_stop()
    return True


class AzureDataExplorer:
    """A event handler class for Azure Data Explorer."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entities_filter: vol.Schema,
    ) -> None:
        """Initialize the listener."""

        self.hass = hass
        self._entry = entry
        self._entities_filter = entities_filter

        self._client = AzureDataExplorerClient(**self._entry.data)
        self._send_interval = self._entry.options[CONF_SEND_INTERVAL]
        self._max_delay = self._entry.options.get(CONF_MAX_DELAY, DEFAULT_MAX_DELAY)

        self._shutdown = False
        self._queue: asyncio.PriorityQueue[  # pylint: disable=unsubscriptable-object
            tuple[int, tuple[datetime, State | None]]
        ] = asyncio.PriorityQueue()
        self._listener_remover: Callable[[], None] | None = None
        self._next_send_remover: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start the component.

        This register the listener and
        schedules the first send.
        """

        self._listener_remover = self.hass.bus.async_listen(
            MATCH_ALL, self.async_listen
        )
        self._schedule_next_send()

    async def async_stop(self) -> None:
        """Shut down the ADX by queueing None, calling send, join queue."""
        if self._next_send_remover:
            self._next_send_remover()
        if self._listener_remover:
            self._listener_remover()
        await self._queue.put(
            (3, (utcnow(), None))
        )  # <---WHY IS THIS NEEDED!!! Creates error when sending none
        await self.async_send(None)
        await self._queue.join()

    def update_options(self, new_options: dict[str, Any]) -> None:
        """Update options."""
        self._send_interval = new_options[CONF_SEND_INTERVAL]

    async def test_connection(self) -> Exception | None:
        """Test the connection to the Azure Data Explorer service."""
        try:
            result = await self.hass.async_add_executor_job(
                self._client.test_connection
            )
            if result is not True:
                raise ConnectionError("result")
        except Exception as exc:
            return exc
        return None

    def _schedule_next_send(self) -> None:
        """Schedule the next send."""
        if not self._shutdown:
            self._next_send_remover = async_call_later(
                self.hass, self._send_interval, self.async_send
            )

    async def async_listen(self, event: Event) -> None:
        """Listen for new messages on the bus and queue them for AEH."""
        if state := event.data.get("new_state"):
            await self._queue.put((2, (event.time_fired, state)))

    async def async_send(self, _) -> None:
        """Write preprocessed events to Azure Data Explorer."""

        adx_events = ""
        while not self._queue.empty():
            _, event = self._queue.get_nowait()
            dropped = 0
            adx_event, dropped = self._parse_event(*event, dropped)
            if dropped == 0:
                adx_events += str(adx_event)

        if adx_events != "":

            try:
                await self.hass.async_add_executor_job(
                    lambda: self._client.ingest_data(adx_events)
                )
            except Exception as err:
                _LOGGER.error(err)

        self._schedule_next_send()

    def _parse_event(
        self,
        time_fired: datetime,
        state: State | None,
        dropped: int,
    ) -> tuple[str | None, int]:
        """Parse event by checking if it needs to be sent, and format it."""
        self._queue.task_done()
        if not state:
            self._shutdown = True
            return None, dropped
        # if state.state in FILTER_STATES or not self._entities_filter(state.entity_id):
        #    return None, dropped
        # if (utcnow() - time_fired).seconds > self._max_delay + self._send_interval:
        #  return None, dropped + 1
        try:
            json_string = bytes(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
            json_dictionary = json.loads(json_string)
            json_event = json.dumps(json_dictionary)
        except Exception as exp:
            _LOGGER.error(exp)
            return ("", 1)

        return (json_event, dropped)
