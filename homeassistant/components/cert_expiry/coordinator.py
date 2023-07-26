"""The cert_expiry component coordinator."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_expiry_timestamp

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[datetime | None]):
    """Class to manage fetching Cert Expiry data from single endpoint."""

    def __init__(self, hass: HomeAssistant, host: str, port) -> None:
        """Initialize global Cert Expiry data updater."""
        self.host = host
        self.port = port
        self.cert_error: str | None = None
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
        """Fetch certificate expiration."""
        try:
            timestamp = await get_cert_expiry_timestamp(self.hass, self.host, self.port)
        except TemporaryFailure as err:
            raise UpdateFailed(err.args[0]) from err
        except ValidationFailure as err:
            self.cert_error = err.args[0]
            self.is_cert_valid = False
            _LOGGER.error("Certificate validation error: %s [%s]", self.host, err)
            return None

        self.cert_error = None
        self.is_cert_valid = True
        return timestamp
