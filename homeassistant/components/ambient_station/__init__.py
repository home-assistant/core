"""Support for Ambient Weather Station Service."""
from __future__ import annotations

from typing import Any

from aioambient import Websocket
from aioambient.errors import WebsocketError
from aioambient.util import get_public_device_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LOCATION,
    ATTR_NAME,
    CONF_API_KEY,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
import homeassistant.helpers.entity_registry as er

from .const import (
    ATTR_LAST_DATA,
    CONF_APP_KEY,
    DOMAIN,
    LOGGER,
    TYPE_SOLARRADIATION,
    TYPE_SOLARRADIATION_LX,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

DATA_CONFIG = "config"

DEFAULT_SOCKET_MIN_RETRY = 15

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@callback
def async_wm2_to_lx(value: float) -> int:
    """Calculate illuminance (in lux)."""
    return round(value / 0.0079)


@callback
def async_hydrate_station_data(data: dict[str, Any]) -> dict[str, Any]:
    """Hydrate station data with addition or normalized data."""
    if (irradiation := data.get(TYPE_SOLARRADIATION)) is not None:
        data[TYPE_SOLARRADIATION_LX] = async_wm2_to_lx(irradiation)

    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Ambient PWS as config entry."""
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_APP_KEY]
        )

    ambient = AmbientStation(
        hass,
        entry,
        Websocket(entry.data[CONF_APP_KEY], entry.data[CONF_API_KEY]),
    )

    try:
        await ambient.ws_connect()
    except WebsocketError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ambient

    async def _async_disconnect_websocket(_: Event) -> None:
        await ambient.websocket.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Ambient PWS config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        ambient = hass.data[DOMAIN].pop(entry.entry_id)
        hass.async_create_task(ambient.ws_disconnect())

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Unique ID format changed, so delete and re-import:
    if version == 1:
        dev_reg = dr.async_get(hass)
        dev_reg.async_clear_config_entry(entry.entry_id)

        en_reg = er.async_get(hass)
        en_reg.async_clear_config_entry(entry.entry_id)

        version = entry.version = 2
        hass.config_entries.async_update_entry(entry)

    LOGGER.info("Migration to version %s successful", version)

    return True


class AmbientStation:
    """Define a class to handle the Ambient websocket."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, websocket: Websocket
    ) -> None:
        """Initialize."""
        self._entry = entry
        self._entry_setup_complete = False
        self._hass = hass
        self._ws_reconnect_delay = DEFAULT_SOCKET_MIN_RETRY
        self.stations: dict[str, dict] = {}
        self.websocket = websocket

    async def ws_connect(self) -> None:
        """Register handlers and connect to the websocket."""

        def on_connect() -> None:
            """Define a handler to fire when the websocket is connected."""
            LOGGER.info("Connected to websocket")

        def on_data(data: dict) -> None:
            """Define a handler to fire when the data is received."""
            mac = data["macAddress"]

            if data == self.stations[mac][ATTR_LAST_DATA]:
                return

            LOGGER.debug("New data received: %s", data)
            self.stations[mac][ATTR_LAST_DATA] = async_hydrate_station_data(data)
            async_dispatcher_send(self._hass, f"ambient_station_data_update_{mac}")

        def on_disconnect() -> None:
            """Define a handler to fire when the websocket is disconnected."""
            LOGGER.info("Disconnected from websocket")

        def on_subscribed(data: dict) -> None:
            """Define a handler to fire when the subscription is set."""
            for station in data["devices"]:
                if (mac := station["macAddress"]) in self.stations:
                    continue

                LOGGER.debug("New station subscription: %s", data)

                self.stations[mac] = {
                    ATTR_LAST_DATA: async_hydrate_station_data(station["lastData"]),
                    ATTR_LOCATION: station.get("info", {}).get("location"),
                    ATTR_NAME: station.get("info", {}).get("name", mac),
                }

            # If the websocket disconnects and reconnects, the on_subscribed
            # handler will get called again; in that case, we don't want to
            # attempt forward setup of the config entry (because it will have
            # already been done):
            if not self._entry_setup_complete:
                self._hass.async_create_task(
                    self._hass.config_entries.async_forward_entry_setups(
                        self._entry, PLATFORMS
                    )
                )
                self._entry_setup_complete = True
            self._ws_reconnect_delay = DEFAULT_SOCKET_MIN_RETRY

        self.websocket.on_connect(on_connect)
        self.websocket.on_data(on_data)
        self.websocket.on_disconnect(on_disconnect)
        self.websocket.on_subscribed(on_subscribed)

        await self.websocket.connect()

    async def ws_disconnect(self) -> None:
        """Disconnect from the websocket."""
        await self.websocket.disconnect()


class AmbientWeatherEntity(Entity):
    """Define a base Ambient PWS entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        ambient: AmbientStation,
        mac_address: str,
        station_name: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._ambient = ambient

        public_device_id = get_public_device_id(mac_address)
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"https://ambientweather.net/dashboard/{public_device_id}"
            ),
            identifiers={(DOMAIN, mac_address)},
            manufacturer="Ambient Weather",
            name=station_name.capitalize(),
        )

        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._mac_address = mac_address
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            if self.entity_description.key == TYPE_SOLARRADIATION_LX:
                self._attr_available = (
                    self._ambient.stations[self._mac_address][ATTR_LAST_DATA][
                        TYPE_SOLARRADIATION
                    ]
                    is not None
                )
            else:
                self._attr_available = (
                    self._ambient.stations[self._mac_address][ATTR_LAST_DATA][
                        self.entity_description.key
                    ]
                    is not None
                )

            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"ambient_station_data_update_{self._mac_address}", update
            )
        )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
