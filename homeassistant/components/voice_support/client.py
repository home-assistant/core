"""Connect to the Voice app and read its capabilities."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

API_VERSION = 1
INFO_TIMEOUT = 10
INFO_REFRESH_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


class InvalidResponseError(Exception):
    """The app returned malformed information."""


CLIENT_ERRORS = (aiohttp.ClientError, TimeoutError, InvalidResponseError)


class UnsupportedVersionError(Exception):
    """The app speaks a protocol version this Home Assistant does not."""

    def __init__(self, info: AppInfo) -> None:
        """Initialize the error."""
        super().__init__(
            f"{info.name} {info.version} speaks protocol version "
            f"{info.api_version}, not {API_VERSION}"
        )
        self.info = info


@dataclass(frozen=True)
class AppInfo:
    """What the app says it is and what it can do."""

    name: str
    version: str
    api_version: int
    wake_words: dict[str, str | None] = field(default_factory=dict)
    """Normalized wake word id -> the phrase said, when it gave one."""

    @staticmethod
    def from_json(data: dict[str, Any]) -> AppInfo:
        """Read an /info response."""
        return AppInfo(
            name=data["name"],
            version=data["version"],
            api_version=data["api_version"],
            wake_words={
                normalize_wake_word(wake_word["id"]): wake_word.get("phrase")
                for wake_word in data["wake_words"]
            },
        )


def normalize_wake_word(wake_word: str) -> str:
    """Treat "Okay Nabu", "okay-nabu" and "okay_nabu" as one wake word."""
    lowered = wake_word.lower().replace("-", "_").replace(" ", "_")
    return "".join(c for c in lowered if c.isalnum() or c == "_")


class VoiceSupportClient:
    """The Voice app at one address and its capabilities."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up a client for the app at this address."""
        self.hass = hass
        self.url = URL.build(scheme="http", host=host, port=port)
        self.info: AppInfo | None = None
        self._stop_refresh: CALLBACK_TYPE | None = None
        self._on_disconnect: CALLBACK_TYPE | None = None

    async def async_connect(self, on_disconnect: CALLBACK_TYPE) -> None:
        """Ask the app what it is, and keep asking now and then.

        An app that is updated, or that goes away and comes back, is only
        noticed by asking again.
        """
        await self.async_update_info()
        self._on_disconnect = on_disconnect
        self._stop_refresh = async_track_time_interval(
            self.hass, self._async_refresh_info, INFO_REFRESH_INTERVAL
        )

    @callback
    def async_close(self) -> None:
        """Stop following the app."""
        if self._stop_refresh is not None:
            self._stop_refresh()
            self._stop_refresh = None

    async def _async_refresh_info(self, _now: datetime | None = None) -> None:
        try:
            await self.async_update_info()
        except (*CLIENT_ERRORS, UnsupportedVersionError) as err:
            _LOGGER.debug("Cannot use the app at %s (%r)", self.url, err)
            if self._on_disconnect is not None:
                self._on_disconnect()

    async def async_update_info(self) -> AppInfo:
        """Ask the app what it is and what it can verify.

        Raises UnsupportedVersionError, besides CLIENT_ERRORS, for an app
        that cannot be used.
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self.url / "info", timeout=aiohttp.ClientTimeout(total=INFO_TIMEOUT)
            ) as response:
                response.raise_for_status()
                try:
                    data = await response.json()
                except ValueError as err:
                    raise InvalidResponseError(
                        "Invalid JSON from the Voice app"
                    ) from err
                try:
                    info = AppInfo.from_json(data)
                except (AttributeError, KeyError, TypeError, ValueError) as err:
                    raise InvalidResponseError(
                        "Invalid info from the Voice app"
                    ) from err
        except CLIENT_ERRORS:
            self.info = None
            raise

        if info.api_version != API_VERSION:
            self.info = None
            raise UnsupportedVersionError(info)

        self.info = info
        _LOGGER.debug(
            "%s %s verifies: %s",
            info.name,
            info.version,
            ", ".join(sorted(info.wake_words)) or "(nothing)",
        )
        return info
