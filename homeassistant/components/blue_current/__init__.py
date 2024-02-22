"""The Blue Current integration."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_API_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, EVSE_ID, LOGGER, MODEL_TYPE

PLATFORMS = [Platform.SENSOR]
CHARGE_POINTS = "CHARGE_POINTS"
DATA = "data"
SMALL_DELAY = 1
LARGE_DELAY = 20

GRID = "GRID"
OBJECT = "object"
VALUE_TYPES = ["CH_STATUS"]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Blue Current as a config entry."""
    hass.data.setdefault(DOMAIN, {})
    client = Client()
    api_token = config_entry.data[CONF_API_TOKEN]
    connector = Connector(hass, config_entry, client)

    try:
        await connector.connect(api_token)
    except InvalidApiToken as err:
        raise ConfigEntryAuthFailed("Invalid API token.") from err
    except BlueCurrentException as err:
        raise ConfigEntryNotReady from err

    hass.async_create_background_task(connector.start_loop(), "blue_current-websocket")
    await client.get_charge_points()

    await client.wait_for_response()
    hass.data[DOMAIN][config_entry.entry_id] = connector
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(connector.disconnect)

    async def _async_disconnect_websocket(_: Event) -> None:
        await connector.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the Blue Current config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class Connector:
    """Define a class that connects to the Blue Current websocket API."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, client: Client
    ) -> None:
        """Initialize."""
        self.config = config
        self.hass = hass
        self.client = client
        self.charge_points: dict[str, dict] = {}
        self.grid: dict[str, Any] = {}
        self.available = False

    async def connect(self, token: str) -> None:
        """Register on_data and connect to the websocket."""
        await self.client.connect(token)
        self.available = True

    async def on_data(self, message: dict) -> None:
        """Handle received data."""

        object_name: str = message[OBJECT]

        # gets charge point ids
        if object_name == CHARGE_POINTS:
            charge_points_data: list = message[DATA]
            await self.handle_charge_point_data(charge_points_data)

        # gets charge point key / values
        elif object_name in VALUE_TYPES:
            value_data: dict = message[DATA]
            evse_id = value_data.pop(EVSE_ID)
            self.update_charge_point(evse_id, value_data)

        # gets grid key / values
        elif GRID in object_name:
            data: dict = message[DATA]
            self.grid = data
            self.dispatch_grid_update_signal()

    async def handle_charge_point_data(self, charge_points_data: list) -> None:
        """Handle incoming chargepoint data."""
        await asyncio.gather(
            *(
                self.handle_charge_point(
                    entry[EVSE_ID], entry[MODEL_TYPE], entry[ATTR_NAME]
                )
                for entry in charge_points_data
            )
        )
        await self.client.get_grid_status(charge_points_data[0][EVSE_ID])

    async def handle_charge_point(self, evse_id: str, model: str, name: str) -> None:
        """Add the chargepoint and request their data."""
        self.add_charge_point(evse_id, model, name)
        await self.client.get_status(evse_id)

    def add_charge_point(self, evse_id: str, model: str, name: str) -> None:
        """Add a charge point to charge_points."""
        self.charge_points[evse_id] = {MODEL_TYPE: model, ATTR_NAME: name}

    def update_charge_point(self, evse_id: str, data: dict) -> None:
        """Update the charge point data."""
        self.charge_points[evse_id].update(data)
        self.dispatch_value_update_signal(evse_id)

    def dispatch_value_update_signal(self, evse_id: str) -> None:
        """Dispatch a value signal."""
        async_dispatcher_send(self.hass, f"{DOMAIN}_value_update_{evse_id}")

    def dispatch_grid_update_signal(self) -> None:
        """Dispatch a grid signal."""
        async_dispatcher_send(self.hass, f"{DOMAIN}_grid_update")

    async def start_loop(self) -> None:
        """Start the receive loop."""
        try:
            await self.client.start_loop(self.on_data)
        except BlueCurrentException as err:
            LOGGER.warning(
                "Disconnected from the Blue Current websocket. Retrying to connect in background. %s",
                err,
            )

            async_call_later(self.hass, SMALL_DELAY, self.reconnect)

    async def reconnect(self, _event_time: datetime | None = None) -> None:
        """Keep trying to reconnect to the websocket."""
        try:
            await self.connect(self.config.data[CONF_API_TOKEN])
            LOGGER.debug("Reconnected to the Blue Current websocket")
            self.hass.async_create_task(self.start_loop())
        except RequestLimitReached:
            self.available = False
            async_call_later(
                self.hass, self.client.get_next_reset_delta(), self.reconnect
            )
        except WebsocketError:
            self.available = False
            async_call_later(self.hass, LARGE_DELAY, self.reconnect)

    async def disconnect(self) -> None:
        """Disconnect from the websocket."""
        with suppress(WebsocketError):
            await self.client.disconnect()
