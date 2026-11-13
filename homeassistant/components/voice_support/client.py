"""Connect to the Voice app and read its capabilities."""

from dataclasses import dataclass, field
from json import JSONDecodeError
import logging
from typing import Any

import aiohttp
import probatio
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_VERSION = 1
INFO_TIMEOUT = 10

INFO_SCHEMA = probatio.Schema(
    {
        "name": str,
        "version": str,
        "api_version": int,
        "wake_words": [
            {
                "id": str,
                probatio.Optional("phrase"): probatio.Any(str, None),
            }
        ],
    },
    required=True,
    extra=probatio.ALLOW_EXTRA,
)

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
        data = INFO_SCHEMA(data)
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
                except JSONDecodeError as err:
                    raise InvalidResponseError(
                        "Invalid JSON from the Voice app"
                    ) from err
                try:
                    info = AppInfo.from_json(data)
                except probatio.Invalid as err:
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
