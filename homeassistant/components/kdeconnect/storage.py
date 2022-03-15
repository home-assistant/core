"""Implementation of a storage to store data for KDE Connect."""
from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509 import Certificate, load_pem_x509_certificate
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.helpers import CertificateHelper
from pykdeconnect.storage import AbstractStorage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_CERT,
    CONF_DEVICE_INCOMING_CAPS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OUTGOING_CAPS,
    CONF_DEVICE_TYPE,
    DOMAIN,
)


class HomeAssistantStorage(AbstractStorage):
    """A storage for home assistant."""

    hass: HomeAssistant
    _devices: dict[str, KdeConnectDevice]
    _device_id: str

    private_key: RSAPrivateKey
    cert: Certificate

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        """Initialize the storage."""
        self.hass = hass
        self._devices = {}
        self._device_id = device_id
        self._config_path = Path(hass.config.path(DOMAIN))

        if not self._config_path.exists():
            self._config_path.mkdir()

        if not self.private_key_path.exists():
            self.private_key = CertificateHelper.generate_private_key()
            CertificateHelper.save_private_key(self.private_key_path, self.private_key)

        if not self.cert_path.exists():
            self.cert = CertificateHelper.generate_cert(
                self.device_id, self.private_key
            )
            CertificateHelper.save_certificate(self.cert_path, self.cert)

    @property
    def device_id(self) -> str:
        """Return this device's device id."""
        return self._device_id

    @property
    def cert_path(self) -> Path:
        """Return the path to this device's ssl certificate."""
        return self._config_path / "certificate.pem"

    @property
    def private_key_path(self) -> Path:
        """Return the path to this device's private key."""
        return self._config_path / "private_key.pem"

    def store_device(self, device: KdeConnectDevice) -> None:
        """Store information on a device."""
        self._devices[device.device_id] = device

    def remove_device(self, device: KdeConnectDevice) -> None:
        """Remove information on a device."""
        if device.device_id in self._devices:
            del self._devices[device.device_id]

    def remove_device_by_id(self, device_id: str) -> None:
        """Remove information on a device using its device id."""
        if device_id in self._devices:
            del self._devices[device_id]

    def load_device(self, device_id: str) -> KdeConnectDevice | None:
        """Load a device from the storage."""
        if device_id in self._devices:
            return self._devices[device_id]

        return None

    def add_device(self, entry: ConfigEntry) -> None:
        """Add a device from a config entry."""
        device_id = entry.data[CONF_DEVICE_ID]

        device_cert = load_pem_x509_certificate(
            entry.data[CONF_DEVICE_CERT].encode("utf-8")
        )

        device = KdeConnectDevice(
            entry.data[CONF_DEVICE_NAME],
            device_id,
            entry.data[CONF_DEVICE_TYPE],
            entry.data[CONF_DEVICE_INCOMING_CAPS],
            entry.data[CONF_DEVICE_OUTGOING_CAPS],
            device_cert,
        )
        self._devices[device_id] = device
