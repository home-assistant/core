"""Encryption key storage for ESPHome devices."""

from __future__ import annotations

import logging
from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

ENCRYPTION_KEY_STORAGE_VERSION = 1
ENCRYPTION_KEY_STORAGE_KEY = "esphome.encryption_keys"


class EncryptionKeyData(TypedDict):
    """Encryption key storage data."""

    keys: dict[str, str]  # MAC address -> base64 encoded key


KEY_ENCRYPTION_STORAGE: HassKey[ESPHomeEncryptionKeyStorage] = HassKey(
    "esphome_encryption_key_storage"
)


class ESPHomeEncryptionKeyStorage:
    """Storage for ESPHome encryption keys."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the encryption key storage."""
        self.hass = hass
        self._store = Store[EncryptionKeyData](
            hass,
            ENCRYPTION_KEY_STORAGE_VERSION,
            ENCRYPTION_KEY_STORAGE_KEY,
            encoder=JSONEncoder,
        )
        self._data: EncryptionKeyData | None = None

    async def async_load(self) -> None:
        """Load encryption keys from storage."""
        if self._data is None:
            data = await self._store.async_load()
            self._data = data or {"keys": {}}

    async def async_save(self) -> None:
        """Save encryption keys to storage."""
        if self._data is not None:
            await self._store.async_save(self._data)

    async def async_get_key(self, mac_address: str) -> str | None:
        """Get encryption key for a MAC address."""
        await self.async_load()
        assert self._data is not None
        return self._data["keys"].get(mac_address.lower())

    async def async_store_key(self, mac_address: str, key: str) -> None:
        """Store encryption key for a MAC address."""
        await self.async_load()
        assert self._data is not None
        self._data["keys"][mac_address.lower()] = key
        await self.async_save()
        _LOGGER.debug(
            "Stored encryption key for device with MAC %s",
            mac_address,
        )

    async def async_remove_key(self, mac_address: str) -> None:
        """Remove encryption key for a MAC address."""
        await self.async_load()
        assert self._data is not None
        lower_mac_address = mac_address.lower()
        if lower_mac_address in self._data["keys"]:
            del self._data["keys"][lower_mac_address]
            await self.async_save()
            _LOGGER.debug(
                "Removed encryption key for device with MAC %s",
                mac_address,
            )


@singleton(KEY_ENCRYPTION_STORAGE, async_=True)
async def async_get_encryption_key_storage(
    hass: HomeAssistant,
) -> ESPHomeEncryptionKeyStorage:
    """Get the encryption key storage instance."""
    storage = ESPHomeEncryptionKeyStorage(hass)
    await storage.async_load()
    return storage
