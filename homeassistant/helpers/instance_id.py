"""Helper to create a unique instance ID."""
from __future__ import annotations

import uuid

from homeassistant.core import HomeAssistant

from . import singleton, storage

DATA_KEY = "core.uuid"
DATA_VERSION = 1

LEGACY_UUID_FILE = ".uuid"


@singleton.singleton(DATA_KEY)
async def async_get(hass: HomeAssistant) -> str:
    """Get unique ID for the hass instance."""
    store = storage.Store(hass, DATA_VERSION, DATA_KEY, True)

    data: dict[str, str] | None = await storage.async_migrator(
        hass,
        hass.config.path(LEGACY_UUID_FILE),
        store,
    )

    if data is not None:
        return data["uuid"]

    data = {"uuid": uuid.uuid4().hex}

    await store.async_save(data)

    return data["uuid"]
