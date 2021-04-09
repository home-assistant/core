"""The cert_expiry component."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_expiry_timestamp

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = CertExpiryDataUpdateCoordinator(hass, host, port)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[datetime]):
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
