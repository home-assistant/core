"""The Azure Data Explorer integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import json
import logging
from multiprocessing import AuthenticationError
from typing import Any

from azure.kusto.data.exceptions import KustoServiceError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
)
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow

from .client import AzureDataExplorerClient
from .const import (
    CONF_FILTER,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DATA_HUB,
    DEFAULT_MAX_DELAY,
    DOMAIN,
    FILTER_STATES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
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
    hass.data[DOMAIN][DATA_FILTER] = yaml_config[DOMAIN][CONF_FILTER]

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
        await adx.test_connection()
    except KustoServiceError as exp:
        _LOGGER.error(exp)
        raise IntegrationError(
            "Could not find Azure Data Explorer database or table"
        ) from exp
    except AuthenticationError as exp:
        _LOGGER.error(exp)
        raise ConfigEntryAuthFailed(
            "Could not authenticate to Azure Data Explorer"
        ) from exp
    except Exception as exp:  # pylint: disable=broad-except
        _LOGGER.error(exp)
        raise ConfigEntryNotReady("Could not connect to Azure Data Explorer") from exp
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

        # self._client = AzureDataExplorerClient(**self._entry.data)

        self._client = AzureDataExplorerClient(
            clusteringesturi=self._entry.data["clusteringesturi"],
            database=self._entry.data["database"],
            table=self._entry.data["table"],
            client_id=self._entry.data["client_id"],
            client_secret=self._entry.data["client_secret"],
            authority_id=self._entry.data["authority_id"],
            use_free_cluster=self._entry.data["use_free_cluster"],
        )

        self._send_interval = self._entry.options[CONF_SEND_INTERVAL]
        self._max_delay = self._entry.options.get(CONF_MAX_DELAY, DEFAULT_MAX_DELAY)

        self._shutdown = False
        self._queue: asyncio.PriorityQueue[
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
        await self._queue.put((3, (utcnow(), None)))
        await self.async_send(None)
        await self._queue.join()

    def update_options(self, new_options: dict[str, Any]) -> None:
        """Update options."""
        self._send_interval = new_options[CONF_SEND_INTERVAL]

    async def test_connection(self) -> None:
        """Test the connection to the Azure Data Explorer service."""
        await self.hass.async_add_executor_job(self._client.test_connection)

        return

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

        adx_events = []
        dropped = 0
        while not self._queue.empty():
            _, event = self._queue.get_nowait()
            adx_event, dropped = self._parse_event(*event, dropped)
            if adx_event is not None:
                adx_events.append(adx_event)
            if dropped:
                _LOGGER.warning(
                    "Dropped %d old events, consider filtering messages", dropped
                )

        if len(adx_events) > 0:

            event_string = "".join(adx_events)

            try:
                await self.hass.async_add_executor_job(
                    self._client.ingest_data, event_string
                )

            except KustoServiceError as err:
                _LOGGER.error("Could not find database or table")
                _LOGGER.error(err)
            except AuthenticationError as err:
                _LOGGER.error("Could not authenticate to Azure Data Explorer")
                _LOGGER.error(err)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Unknown error")
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
            return None, dropped + 1
        if state.state in FILTER_STATES or not self._entities_filter(state.entity_id):
            return None, dropped + 1
        if (utcnow() - time_fired).seconds > self._max_delay + self._send_interval:
            return None, dropped + 1
        try:
            json_string = bytes(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
            json_dictionary = json.loads(json_string)
            json_event = json.dumps(json_dictionary)
        except Exception as exp:  # pylint: disable=broad-except
            _LOGGER.error(exp)
            return (None, dropped + 1)

        return (json_event, dropped)
