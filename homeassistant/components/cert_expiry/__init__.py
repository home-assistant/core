"""The cert_expiry component."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_expiry_timestamp

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = CertExpiryDataUpdateCoordinator(hass, host, port)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    async def async_finish_startup(_):
        await coordinator.async_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.state == CoreState.running:
        await async_finish_startup(None)
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, async_finish_startup
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[Optional[datetime]]):
    """Class to manage fetching Cert Expiry data from single endpoint."""

    def __init__(self, hass, host, port):
        """Initialize global Cert Expiry data updater."""
        self.host = host
        self.port = port
        self.cert_error = None
        self.is_cert_valid = False

        display_port = f":{port}" if port != DEFAULT_PORT else ""
        name = f"{self.host}{display_port}"

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> datetime | None:
        """Fetch certificate."""
        try:
            timestamp = await get_cert_expiry_timestamp(self.hass, self.host, self.port)
        except TemporaryFailure as err:
            raise UpdateFailed(err.args[0]) from err
        except ValidationFailure as err:
            self.cert_error = err
            self.is_cert_valid = False
            _LOGGER.error("Certificate validation error: %s [%s]", self.host, err)
            return None

        self.cert_error = None
        self.is_cert_valid = True
        return timestamp
