"""Home Assistant-aware ESPHome serial proxy URI handler for serialx."""

from __future__ import annotations

import asyncio
from typing import cast

from aioesphomeapi import APIClient
from serialx import register_uri_handler
from serialx.platforms.serial_esphome import (
    ESPHomeSerial,
    ESPHomeSerialTransport,
    InvalidSettingsError,
)
from yarl import URL

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, async_get_hass

from .const import DOMAIN
from .entry_data import ESPHomeConfigEntry

SCHEME = "esphome-hass://"

# This is required so that serialx can safely query Core for an instance of an
# aioesphomeapi client. We cannot make any assumptions here, some packages run separate
# asyncio event loops in dedicated threads.
_HASS_LOOP: asyncio.AbstractEventLoop | None = None


def set_hass_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store a reference to the Core event loop."""
    global _HASS_LOOP  # noqa: PLW0603  # pylint: disable=global-statement
    _HASS_LOOP = loop


def build_url(entry_id: str, port_name: str) -> URL:
    """Build a canonical `esphome-hass://` URL."""
    return URL.build(
        scheme="esphome-hass",
        host="esphome",
        path=f"/{entry_id}",
        query={"port_name": port_name},
    )


async def _resolve_client(entry_id: str) -> APIClient:
    """Look up the `APIClient` for a specific config entry."""

    # This function is async specifically so that we can get a reference to the Home
    # Assistant Core instance from its own thread
    hass: HomeAssistant = async_get_hass()
    entry = cast(ESPHomeConfigEntry, hass.config_entries.async_get_entry(entry_id))

    if entry is None or entry.domain != DOMAIN:
        raise InvalidSettingsError(f"No ESPHome config entry with id {entry_id!r}")

    if entry.state is not ConfigEntryState.LOADED:
        raise InvalidSettingsError(f"ESPHome config entry {entry_id!r} is not loaded")

    return entry.runtime_data.client


class HassESPHomeSerial(ESPHomeSerial):
    """ESPHomeSerial that resolves an HA config entry's APIClient from the URL."""

    _api: APIClient | None
    _path: str | None

    async def _async_open(self) -> None:
        """Resolve the HA config entry's APIClient, then open the proxy."""
        if self._api is None and self._path is not None:
            parsed = URL(str(self._path))

            entry_id = parsed.path.lstrip("/")
            if not entry_id:
                raise InvalidSettingsError(
                    f"No ESPHome config entry id in URL {self._path!r}"
                )

            if "port_name" not in parsed.query:
                raise InvalidSettingsError("Port name is required")

            self._port_name = parsed.query["port_name"]

            hass_loop = _HASS_LOOP
            if hass_loop is None:
                raise InvalidSettingsError(
                    "ESPHome integration has not registered its event loop"
                )

            # Fetch the `APIClient` from the Core via the appropriate event loop
            self._api = await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(_resolve_client(entry_id), hass_loop)
            )
            self._client_loop = self._api._loop  # noqa: SLF001

        await super()._async_open()


class HassESPHomeSerialTransport(ESPHomeSerialTransport):
    """Transport variant that constructs :class:`HassESPHomeSerial`."""

    transport_name = "esphome-hass"
    _serial_cls = HassESPHomeSerial


register_uri_handler(
    scheme=SCHEME,
    unique_scheme=SCHEME,
    sync_cls=HassESPHomeSerial,
    async_transport_cls=HassESPHomeSerialTransport,
)
