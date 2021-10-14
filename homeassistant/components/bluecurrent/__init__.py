"""The BlueCurrent integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_call_later

from .const import (
    CHARGE_POINTS,
    DATA,
    DELAY_1,
    DELAY_2,
    DOMAIN,
    EVSE_ID,
    GRID_STATUS,
    LOGGER,
    MODEL_TYPE,
    OBJECT,
    PLATFORMS,
    VALUE_TYPES,
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Blue Current as a config entry."""
    hass.data.setdefault(DOMAIN, {})
    client = Client()
    api_token = config_entry.data[CONF_API_TOKEN]
    connector = Connector(hass, config_entry, client)
    try:
        await connector.connect(api_token)
    except (BlueCurrentException) as err:
        if isinstance(err, InvalidApiToken):
            raise ConfigEntryAuthFailed("Invalid api token.") from err
        raise ConfigEntryNotReady from err

    hass.loop.create_task(connector.start_loop())
    await client.get_charge_points()

    await client.wait_for_response()
    hass.data[DOMAIN][config_entry.entry_id] = connector
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    async def _async_disconnect_websocket(_: Event) -> None:
        await connector.disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the BlueCurrent config entry."""
    connector: Connector = hass.data[DOMAIN].pop(config_entry.entry_id)
    hass.async_create_task(connector.disconnect())

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


def set_entities_unavalible(hass: HomeAssistant, config_id: str) -> None:
    """Set all Blue Current entities to unavailable."""
    registry = entity_registry.async_get(hass)
    entries = entity_registry.async_entries_for_config_entry(registry, config_id)

    for entry in entries:
        entry.write_unavailable_state(hass)


class Connector:
    """Define a class that connects to the Blue Current websocket API."""

    charge_points: dict[str, dict] = {}
    grid: dict[str, Any] = {}

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, client: Client
    ) -> None:
        """Initialize."""
        self._config: ConfigEntry = config
        self._hass: HomeAssistant = hass
        self.client: Client = client

    async def connect(self, token: str) -> None:
        """Register on_data and connect to the websocket."""
        await self.client.connect(token)

    async def on_data(self, message: dict) -> None:
        """Handle received data."""

        async def handle_charge_points(data: list) -> None:
            """Loop over the charge points and get their data."""
            for entry in data:
                evse_id = entry[EVSE_ID]
                model = entry[MODEL_TYPE]
                self.add_charge_point(evse_id, model)
                await self.get_charge_point_data(evse_id)
            await self.client.get_grid_status(data[0][EVSE_ID])

        object_name: str = message[OBJECT]

        if DATA in message:
            data: dict | list = message[DATA]

        # gets charge point ids
        if object_name == CHARGE_POINTS:
            assert isinstance(data, list)
            await handle_charge_points(data)

        # gets charge point key / values
        elif object_name in VALUE_TYPES:
            assert isinstance(data, dict)
            evse_id = data.pop(EVSE_ID)
            self.update_charge_point(evse_id, data)

        # gets grid key / values
        elif object_name == GRID_STATUS:
            assert isinstance(data, dict)
            self.grid = data
            self.dispatch_signal()

    async def get_charge_point_data(self, evse_id: str) -> None:
        """Get all the data of a charge point."""
        await self.client.get_status(evse_id)

    def add_charge_point(self, evse_id: str, model: str) -> None:
        """Add a charge point to charge_points."""
        self.charge_points[evse_id] = {MODEL_TYPE: model}

    def update_charge_point(self, evse_id: str, data: dict) -> None:
        """Update the charge point data."""
        for key in data:
            self.charge_points[evse_id][key] = data[key]
        self.dispatch_signal(evse_id)

    def dispatch_signal(self, evse_id: str | None = None) -> None:
        """Dispatch a signal."""
        if evse_id is not None:
            async_dispatcher_send(self._hass, f"{DOMAIN}_value_update_{evse_id}")
        else:
            async_dispatcher_send(self._hass, f"{DOMAIN}_grid_update")

    async def start_loop(self) -> None:
        """Start the receive loop."""
        try:
            await self.client.start_loop(self.on_data)
        except (BlueCurrentException) as err:
            LOGGER.warning(
                "Disconnected from the Blue Current websocket. Retrying to connect in background. %s",
                err,
            )

            async_call_later(self._hass, DELAY_1, self.reconnect)

    async def reconnect(self, event_time: datetime | None = None) -> None:
        """Keep trying to reconnect to the websocket."""
        try:
            await self.connect(self._config.data[CONF_API_TOKEN])
            LOGGER.warning("Reconnected to the Blue Current websocket")
            self._hass.loop.create_task(self.start_loop())
            await self.client.get_charge_points()
        except (WebsocketException, RequestLimitReached) as err:
            set_entities_unavalible(self._hass, self._config.entry_id)
            if isinstance(err, RequestLimitReached):
                delay = self.client.get_next_reset_delta()
            else:
                delay = DELAY_2
            async_call_later(self._hass, delay, self.reconnect)

    async def disconnect(self) -> None:
        """Disconnect from the websocket."""
        try:
            await self.client.disconnect()
        except WebsocketException:
            pass


class BlueCurrentEntity(Entity):
    """Define a base charge point entity."""

    def __init__(self, connector: Connector, evse_id: str | None = None) -> None:
        """Initialize the entity."""
        self._connector: Connector = connector

        if evse_id:
            self._evse_id = evse_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, evse_id)},
                name=evse_id,
                manufacturer="BlueCurrent",
                model=connector.charge_points[evse_id][MODEL_TYPE],
            )
            self.is_grid = False
        else:
            self.is_grid = True

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        if self.is_grid:
            self.async_on_remove(
                async_dispatcher_connect(self.hass, f"{DOMAIN}_grid_update", update)
            )
        else:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, f"{DOMAIN}_value_update_{self._evse_id}", update
                )
            )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
