"""Keeps a live connection to the CoolBot cloud and publishes state to entities."""

import logging
from typing import override

from pycoolbot import CoolbotAuthError, CoolbotClient, CoolbotDevice, CoolbotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STALE_AFTER_SECONDS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type CoolbotConfigEntry = ConfigEntry[CoolbotCoordinator]


class CoolbotCoordinator(DataUpdateCoordinator[dict[str, CoolbotDevice]]):
    """Maintains one socket to the CoolBot cloud for a config entry.

    The cloud pushes readings continuously, so this does not poll the service. It
    reads the client's already-received state on a short interval and hands it to
    entities, which also serves as the keepalive.

    Reconnection is handled here rather than in the library: a CoolBot drops off
    and returns every few minutes, and the socket does not always survive that.
    """

    config_entry: CoolbotConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CoolbotConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._client: CoolbotClient | None = None

    @override
    async def _async_setup(self) -> None:
        """Establish the first connection, before the initial refresh."""
        await self._async_connect()

    async def _async_connect(self) -> None:
        session = async_get_clientsession(self.hass)
        client = CoolbotClient(
            self.config_entry.data[CONF_EMAIL],
            self.config_entry.data[CONF_PASSWORD],
            session=session,
        )
        try:
            await client.async_connect()
        except CoolbotAuthError as err:
            # Prompts the user to re-enter credentials rather than retrying forever.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except CoolbotError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._client = client

    @override
    async def _async_update_data(self) -> dict[str, CoolbotDevice]:
        if self._client is None or not self._client.connected:
            _LOGGER.debug("Socket is down, reconnecting")
            await self._async_shutdown_client()
            await self._async_connect()

        assert self._client is not None
        try:
            # Never block a refresh waiting for a push; freshness is conveyed by
            # each device's data_age_seconds instead.
            devices = await self._client.async_get_devices(wait_for_live=False)
            await self._client.async_ping()
        except CoolbotAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except CoolbotError as err:
            # Drop the socket so the next refresh reconnects from scratch.
            await self._async_shutdown_client()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not devices:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_devices")

        return {device.unique_id: device for device in devices}

    @override
    async def async_shutdown(self) -> None:
        """Stop refreshing and close the socket."""
        await super().async_shutdown()
        await self._async_shutdown_client()

    async def _async_shutdown_client(self) -> None:
        if self._client is not None:
            try:
                await self._client.async_close()
            except Exception:
                _LOGGER.debug("Error while closing the socket", exc_info=True)
            self._client = None


def device_is_fresh(device: CoolbotDevice) -> bool:
    """Whether a device's readings should be trusted right now.

    A CoolBot that loses WiFi leaves the cloud serving its last known values, so
    a stale reading looks current. Entities go unavailable rather than reporting
    a temperature that has stopped moving.
    """
    if not device.is_provisioned:
        return False
    age = device.data_age_seconds
    if age is None:
        # No live push seen yet this session; fall back to the account's own view.
        return device.available
    return age <= STALE_AFTER_SECONDS
