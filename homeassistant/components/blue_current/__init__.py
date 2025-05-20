"""The Blue Current integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, EVSE_ID, LOGGER, MODEL_TYPE

type BlueCurrentConfigEntry = ConfigEntry[Connector]

PLATFORMS = [Platform.SENSOR]
CHARGE_POINTS = "CHARGE_POINTS"
DATA = "data"
DELAY = 5

GRID = "GRID"
OBJECT = "object"
VALUE_TYPES = ["CH_STATUS"]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: BlueCurrentConfigEntry
) -> bool:
    """Set up Blue Current as a config entry."""
    client = Client()
    api_token = config_entry.data[CONF_API_TOKEN]
    connector = Connector(hass, config_entry, client)

    try:
        await client.validate_api_token(api_token)
    except InvalidApiToken as err:
        raise ConfigEntryAuthFailed("Invalid API token.") from err
    except BlueCurrentException as err:
        raise ConfigEntryNotReady from err
    config_entry.async_create_background_task(
        hass, connector.run_task(), "blue_current-websocket"
    )

    await client.wait_for_charge_points()
    config_entry.runtime_data = connector
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: BlueCurrentConfigEntry
) -> bool:
    """Unload the Blue Current config entry."""

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


class Connector:
    """Define a class that connects to the Blue Current websocket API."""

    def __init__(
        self, hass: HomeAssistant, config: BlueCurrentConfigEntry, client: Client
    ) -> None:
        """Initialize."""
        self.config = config
        self.hass = hass
        self.client = client
        self.charge_points: dict[str, dict] = {}
        self.grid: dict[str, Any] = {}

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
            ),
            self.client.get_grid_status(charge_points_data[0][EVSE_ID]),
        )

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
        self.dispatch_charge_point_update_signal(evse_id)

    def dispatch_charge_point_update_signal(self, evse_id: str) -> None:
        """Dispatch a charge point update signal."""
        async_dispatcher_send(self.hass, f"{DOMAIN}_charge_point_update_{evse_id}")

    def dispatch_grid_update_signal(self) -> None:
        """Dispatch a grid update signal."""
        async_dispatcher_send(self.hass, f"{DOMAIN}_grid_update")

    async def on_open(self) -> None:
        """Fetch data when connection is established."""
        await self.client.get_charge_points()

    async def run_task(self) -> None:
        """Start the receive loop."""
        try:
            while True:
                try:
                    await self.client.connect(self.on_data, self.on_open)
                except RequestLimitReached:
                    LOGGER.warning(
                        "Request limit reached. reconnecting at 00:00 (Europe/Amsterdam)"
                    )
                    delay = self.client.get_next_reset_delta().seconds
                except WebsocketError:
                    LOGGER.debug("Disconnected, retrying in background")
                    delay = DELAY

                self._on_disconnect()
                await asyncio.sleep(delay)
        finally:
            await self._disconnect()

    def _on_disconnect(self) -> None:
        """Dispatch signals to update entity states."""
        for evse_id in self.charge_points:
            self.dispatch_charge_point_update_signal(evse_id)
        self.dispatch_grid_update_signal()

    async def _disconnect(self) -> None:
        """Disconnect from the websocket."""
        with suppress(WebsocketError):
            await self.client.disconnect()
            self._on_disconnect()

    @property
    def connected(self) -> bool:
        """Returns the connection status."""
        return self.client.is_connected()
