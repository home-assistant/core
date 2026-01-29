"""DataUpdateCoordinator for WLED."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wled import (
    WLED,
    Device as WLEDDevice,
    Releases,
    WLEDConnectionClosedError,
    WLEDError,
    WLEDReleases,
    WLEDUnsupportedVersionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_KEEP_MAIN_LIGHT,
    DEFAULT_KEEP_MAIN_LIGHT,
    DOMAIN,
    LOGGER,
    RELEASES_SCAN_INTERVAL,
    SCAN_INTERVAL,
)

type WLEDConfigEntry = ConfigEntry[WLEDDataUpdateCoordinator]


def normalize_mac_address(mac: str) -> str:
    """Normalize a MAC address to lowercase without separators.

    This format is used by WLED firmware as well as unique IDs in Home Assistant.

    The homeassistant.helpers.device_registry.format_mac function is preferred but
    returns MAC addresses with colons as separators.
    """
    return mac.lower().replace(":", "").replace(".", "").replace("-", "").strip()


class WLEDDataUpdateCoordinator(DataUpdateCoordinator[WLEDDevice]):
    """Class to manage fetching WLED data from single endpoint."""

    keep_main_light: bool
    config_entry: WLEDConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: WLEDConfigEntry,
    ) -> None:
        """Initialize global WLED data updater."""
        self.keep_main_light = entry.options.get(
            CONF_KEEP_MAIN_LIGHT, DEFAULT_KEEP_MAIN_LIGHT
        )
        self.wled = WLED(entry.data[CONF_HOST], session=async_get_clientsession(hass))
        self.unsub: CALLBACK_TYPE | None = None

        if TYPE_CHECKING:
            assert entry.unique_id
        self.config_mac_address = normalize_mac_address(entry.unique_id)

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @property
    def has_main_light(self) -> bool:
        """Return if the coordinated device has a main light."""
        return self.keep_main_light or (
            self.data is not None and len(self.data.state.segments) > 1
        )

    @callback
    def _use_websocket(self) -> None:
        """Use WebSocket for updates, instead of polling."""

        async def listen() -> None:
            """Listen for state changes via WebSocket."""
            try:
                await self.wled.connect()
            except WLEDError as err:
                self.logger.info(err)
                if self.unsub:
                    self.unsub()
                    self.unsub = None
                return

            try:
                await self.wled.listen(callback=self.async_set_updated_data)
            except WLEDConnectionClosedError as err:
                self.last_update_success = False
                self.logger.info(err)
            except WLEDError as err:
                self.last_update_success = False
                self.async_update_listeners()
                self.logger.error(err)

            # Ensure we are disconnected
            await self.wled.disconnect()
            if self.unsub:
                self.unsub()
                self.unsub = None

        async def close_websocket(_: Event) -> None:
            """Close WebSocket connection."""
            self.unsub = None
            await self.wled.disconnect()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

        # Start listening
        self.config_entry.async_create_background_task(
            self.hass, listen(), "wled-listen"
        )

    async def _async_update_data(self) -> WLEDDevice:
        """Fetch data from WLED."""
        try:
            device = await self.wled.update()
        except WLEDUnsupportedVersionError as error:
            # Error message from WLED library contains version info
            # better to show that to user, but it is not translatable.
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_version",
                translation_placeholders={"error": str(error)},
            ) from error
        except WLEDError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_wled_error",
                translation_placeholders={"error": str(error)},
            ) from error

        device_mac_address = normalize_mac_address(device.info.mac_address)
        if device_mac_address != self.config_mac_address:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="mac_address_mismatch",
                translation_placeholders={
                    "expected_mac": format_mac(self.config_mac_address).upper(),
                    "actual_mac": format_mac(device_mac_address).upper(),
                },
            )

        # If the device supports a WebSocket, try activating it.
        if (
            device.info.websocket is not None
            and not self.wled.connected
            and not self.unsub
        ):
            self._use_websocket()

        return device


class WLEDReleasesDataUpdateCoordinator(DataUpdateCoordinator[Releases]):
    """Class to manage fetching WLED releases."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global WLED releases updater."""
        self.wled = WLEDReleases(session=async_get_clientsession(hass))
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=RELEASES_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Releases:
        """Fetch release data from WLED."""
        try:
            return await self.wled.releases()
        except WLEDError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_github_error",
                translation_placeholders={"error": str(error)},
            ) from error
