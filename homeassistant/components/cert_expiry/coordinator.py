"""DataUpdateCoordinator for cert_expiry coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_PORT
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert, get_cert_expiry_timestamp, verify_cert

_LOGGER = logging.getLogger(__name__)

type CertExpiryConfigEntry = ConfigEntry[CertExpiryDataUpdateCoordinator]


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[datetime | None]):
    """Class to manage fetching Cert Expiry data from single endpoint."""

    hass: HomeAssistant
    config_entry: CertExpiryConfigEntry
    host: str
    port: int
    validate_cert_full: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CertExpiryConfigEntry,
        host: str,
        port: int,
        validate_cert_full: bool,
    ) -> None:
        """Initialize global Cert Expiry data updater."""
        self.host = host
        self.port = port
        self.validate_cert_full = validate_cert_full
        self.cert_error: ValidationFailure | None = None
        self.is_cert_expired: bool = False
        self.is_cert_valid = False

        display_port = f":{port}" if port != DEFAULT_PORT else ""
        name = f"{self.host}{display_port}"

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(hours=12),
            always_update=False,
        )

    async def _async_update_data(self) -> datetime | None:
        """Fetch certificate."""
        try:
            cert, peer_certs = await get_cert(
                self.hass,
                self.host,
                self.port,
            )
        except TemporaryFailure as err:
            raise UpdateFailed(err.args[0]) from err
        except ValidationFailure as err:
            self.cert_error = err
            self.is_cert_valid = False
            self.is_cert_expired = False
            _LOGGER.error("Certificate loading error: %s [%s]", self.host, err)
            return None
        timestamp: datetime = get_cert_expiry_timestamp(cert, self.host, self.port)

        if timestamp < dt_util.utcnow():
            self.cert_error = ValidationFailure(f"Certificate expired at: {timestamp}")
            self.is_cert_expired = True
        else:
            self.cert_error = None
            self.is_cert_expired = False

        if self.validate_cert_full:
            try:
                verify_cert(cert, peer_certs, self.host)
                self.is_cert_valid = True
                self.cert_error = None
            except ValidationFailure as err:
                self.is_cert_valid = False
                self.cert_error = err
                _LOGGER.error("Certificate validation error: %s [%s]", self.host, err)
        else:
            self.is_cert_valid = not self.is_cert_expired

        return timestamp
