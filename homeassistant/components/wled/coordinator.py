"""DataUpdateCoordinator for WLED."""

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
from wled.const import DEFAULT_REPO

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


def normalize_repo(repo: str | None) -> str:
    """Normalize a WLED repository name."""
    if repo is None:
        return DEFAULT_REPO

    normalized_repo = repo.strip().lower()
    if normalized_repo == DEFAULT_REPO.lower():
        return DEFAULT_REPO

    return normalized_repo or DEFAULT_REPO


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


class WLEDReleasesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Releases]]):
    """Class to manage fetching WLED releases."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global WLED releases updater."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=RELEASES_SCAN_INTERVAL,
        )
        self._repos_by_entry_id: dict[str, str] = {}

    async def async_set_repo(self, entry_id: str, repo: str | None) -> None:
        """Set the repository currently used by a WLED config entry."""
        normalized_repo = normalize_repo(repo)
        if self._repos_by_entry_id.get(entry_id) == normalized_repo:
            return

        self._repos_by_entry_id[entry_id] = normalized_repo
        await self.async_request_refresh()

    @callback
    def async_unset_repo(self, entry_id: str) -> None:
        """Stop tracking the repository used by a WLED config entry."""
        repo = self._repos_by_entry_id.pop(entry_id, None)
        if repo is None or repo in self._repos_by_entry_id.values():
            return

        if self.data is not None and repo in self.data:
            self.data = {key: value for key, value in self.data.items() if key != repo}
            self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, Releases]:
        """Fetch release data from WLED."""
        active_repos = set(self._repos_by_entry_id.values())
        releases_by_repo = {
            repo: releases
            for repo, releases in (self.data or {}).items()
            if repo in active_repos
        }

        # Preserve existing release data for repos with transient fetch failures,
        # while dropping repos that are no longer used by any WLED entry.
        first_error: WLEDError | None = None
        success_count = 0
        for repo in active_repos:
            try:
                releases_by_repo[repo] = await WLEDReleases(
                    repo=repo,
                    session=async_get_clientsession(self.hass),
                ).releases()
            except WLEDError as error:
                first_error = first_error or error
                self.logger.warning(
                    "Error fetching WLED releases for repo %s: %s", repo, error
                )
            else:
                success_count += 1

        if active_repos and not success_count:
            assert first_error is not None
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_github_error",
                translation_placeholders={"error": str(first_error)},
            ) from first_error

        return releases_by_repo
