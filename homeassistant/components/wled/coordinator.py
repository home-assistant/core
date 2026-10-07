"""DataUpdateCoordinator for WLED."""

from typing import TYPE_CHECKING, Any, override

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


def _led_setup(device: WLEDDevice) -> tuple[Any, ...] | None:
    """Return what of the LED setup the color modes depend on, if known."""
    if (led_config := device.led_config) is None:
        return None

    return (
        led_config.cct_from_rgb,
        tuple(
            (
                output.start,
                output.length,
                output.has_rgb,
                output.has_white,
                output.has_cct,
            )
            for output in led_config.outputs
        ),
    )


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
        # The LED setup the lights set up their color modes from, if known.
        self._led_setup: tuple[Any, ...] | None = None

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

    def _led_setup_changed(self, device: WLEDDevice) -> bool:
        """Return whether the LED setup the color modes came from changed.

        A setup that isn't known right now, like when fetching it failed,
        doesn't count: that would reload the integration twice for nothing.
        """
        # A segment can do other colors, like after changing the LED type.
        old_segments = self.data.state.segments
        if any(
            segment_id in old_segments
            and old_segments[segment_id].light_capabilities
            != segment.light_capabilities
            for segment_id, segment in device.state.segments.items()
        ):
            return True

        led_setup = _led_setup(device)
        return led_setup is not None and led_setup != self._led_setup

    @property
    def has_main_light(self) -> bool:
        """Return if the coordinated device has a main light."""
        return self.keep_main_light or (
            self.data is not None and len(self.data.state.segments) > 1
        )

    @property
    def segment_ids(self) -> set[int]:
        """Return the set of segment IDs."""
        return {
            segment.segment_id
            for segment in self.data.state.segments.values()
            if segment.segment_id is not None
        }

    @callback
    def _use_websocket(self) -> None:
        """Use WebSocket for updates, instead of polling."""

        async def listen() -> None:
            """Listen for state changes via WebSocket."""
            try:
                try:
                    await self.wled.connect()
                except WLEDError as err:
                    self.logger.info(err)
                    return

                try:
                    # Stop polling as long as we have a websocket. WS will push
                    # updates to us
                    self.update_interval = None
                    await self.wled.listen(callback=self.async_set_updated_data)
                except WLEDConnectionClosedError as err:
                    self.last_update_success = False
                    self.logger.info(err)
                except WLEDError as err:
                    self.last_update_success = False
                    self.async_update_listeners()
                    self.logger.error(err)
                finally:
                    # Pull data immediately and restart polling
                    self.update_interval = SCAN_INTERVAL
                    self.hass.async_create_task(self.async_request_refresh())

                # Ensure we are disconnected
                await self.wled.disconnect()
            finally:
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

    @override
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

        # Firmware from another repository changes which updates can be offered,
        # like after flashing a fork; a changed LED setup changes the color
        # modes of the lights. Set the integration up again for either.
        previous: WLEDDevice | None = self.data
        if previous is None:
            # Nothing to compare with yet; remember what the lights start from.
            self._led_setup = _led_setup(device)
        elif device.info.repo != previous.info.repo or self._led_setup_changed(device):
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

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

    def __init__(self, hass: HomeAssistant, repo: str) -> None:
        """Initialize the WLED releases updater for a firmware repository."""
        self.repo = repo
        self.wled = WLEDReleases(session=async_get_clientsession(hass), repo=repo)
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=RELEASES_SCAN_INTERVAL,
        )

    @override
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
