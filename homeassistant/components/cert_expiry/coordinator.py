"""DataUpdateCoordinator for cert_expiry coordinator."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import client_context

from .certs import CertificateInfo, HandshakePolicyVerifier, async_get_cert
from .const import DEFAULT_PORT, DOMAIN
from .errors import CertExpiryException

_LOGGER = logging.getLogger(__name__)

type CertExpiryConfigEntry = ConfigEntry[CertExpiryDataUpdateCoordinator]


@dataclass(frozen=True)
class CertExpiryData:
    """Everything a cert_expiry entity needs from one successful check."""

    certificate: CertificateInfo
    tls_version: str | None
    cipher_name: str | None
    tls_version_error: str | None
    cipher_error: str | None
    cert_error: str | None

    @property
    def expires_at(self) -> datetime:
        """Return when the certificate expires."""
        return self.certificate.not_valid_after

    @property
    def errors(self) -> list[str]:
        """Return the verification errors that are set."""
        return [
            error
            for error in (
                self.tls_version_error,
                self.cipher_error,
                self.cert_error,
            )
            if error
        ]

    @property
    def validity_reason(self) -> str | None:
        """Return why now is outside the validity period, or None if inside it."""
        now = dt_util.utcnow()
        if now > self.certificate.not_valid_after:
            return "expired"
        if now < self.certificate.not_valid_before:
            return "not_yet_valid"
        return None

    @property
    def is_valid(self) -> bool:
        """Return whether now is inside the certificate's validity period."""
        return self.validity_reason is None

    @property
    def has_problem(self) -> bool:
        """Return whether any check failed or the certificate is outside its validity period."""
        return bool(self.errors) or not self.is_valid

    @property
    def problem_reason(self) -> str | None:
        """Return the reason for the first problem found, or None if there isn't one."""
        return self.validity_reason or next(iter(self.errors), None)


class CertExpiryDataUpdateCoordinator(DataUpdateCoordinator[CertExpiryData]):
    """Class to manage fetching Cert Expiry data from single endpoint."""

    config_entry: CertExpiryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CertExpiryConfigEntry,
        host: str,
        port: int,
    ) -> None:
        """Initialize global Cert Expiry data updater."""
        self.host = host
        self.port = port
        self._verifier = HandshakePolicyVerifier(client_context(), host)

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

    @override
    async def _async_update_data(self) -> CertExpiryData:
        """Fetch certificate."""
        try:
            result = await async_get_cert(self.hass, self.host, self.port)
        except CertExpiryException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err

        verifier = self._verifier
        return CertExpiryData(
            certificate=CertificateInfo.from_certificate(result.cert),
            tls_version=result.tls_version,
            cipher_name=result.cipher_name,
            tls_version_error=verifier.verify_tls_version(result.tls_version),
            cipher_error=verifier.verify_cipher(
                result.cipher_name, result.cipher_protocol
            ),
            cert_error=verifier.verify_cert(result.cert, result.intermediates),
        )
