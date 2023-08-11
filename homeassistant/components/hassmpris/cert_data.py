"""Code to persist and restore certificate data."""

import os.path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.x509 import Certificate

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_CLIENT_CERT, CONF_CLIENT_KEY, CONF_TRUST_CHAIN


def _load_cert_chain(chain: bytes) -> list[Certificate]:
    start_line = b"-----BEGIN CERTIFICATE-----"
    cert_slots = chain.split(start_line)
    certificates: list[Certificate] = []
    for single_pem_cert in cert_slots[1:]:
        loaded = x509.load_pem_x509_certificate(start_line + single_pem_cert)
        certificates.append(loaded)
    return certificates


class CertStore(Store):
    """A store for certificate data used by AsyncMPRISClient."""

    def __init__(self, hass: HomeAssistant, unique_id: str) -> None:
        """Initialize the certificate store."""
        self.unique_id = unique_id
        Store.__init__(self, hass, 1, "hassmpris" + os.path.sep + unique_id, True)

    async def load_cert_data(
        self,
    ) -> tuple[Certificate, PrivateKeyTypes, list[Certificate]]:
        """Retrieve client cert, key, and trust chain for an entry.

        Raises KeyError if the data could not be loaded because
        it is absent.
        """
        data = await self.async_load()
        if data is None:
            raise KeyError(self.unique_id)
        client_cert = x509.load_pem_x509_certificate(
            data[CONF_CLIENT_CERT].encode("ascii"),
        )
        client_key = serialization.load_pem_private_key(
            data[CONF_CLIENT_KEY].encode("ascii"),
            None,
        )
        trust_chain = _load_cert_chain(
            data[CONF_TRUST_CHAIN].encode("ascii"),
        )
        return client_cert, client_key, trust_chain

    async def save_cert_data(
        self,
        client_cert: Certificate,
        client_key: PrivateKeyTypes,
        trust_chain: list[Certificate],
    ) -> None:
        """Persist client cert, key, and trust chain for an entry."""
        data = {
            CONF_CLIENT_CERT: client_cert.public_bytes(
                serialization.Encoding.PEM
            ).decode("ascii"),
            CONF_CLIENT_KEY: client_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("ascii"),
            CONF_TRUST_CHAIN: "\n".join(
                x.public_bytes(serialization.Encoding.PEM).decode("ascii")
                for x in trust_chain
            ),
        }
        await self.async_save(data)

    async def remove_cert_data(
        self,
    ) -> None:
        """Remove client cert, key, and trust chain for an entry."""
        await self.async_remove()
