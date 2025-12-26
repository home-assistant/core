"""Tests for Sure Petcare integration."""

from unittest.mock import AsyncMock

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.components.surepetcare.coordinator import SurePetcareDataCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOUSEHOLD_ID = 987654321
HUB_ID = 123456789

MOCK_HUB = {
    "id": HUB_ID,
    "product_id": 1,
    "household_id": HOUSEHOLD_ID,
    "name": "Hub",
    "status": {
        "led_mode": 0,
        "pairing_mode": 0,
        "online": True,
    },
}

MOCK_FEEDER = {
    "id": 12345,
    "product_id": 4,
    "household_id": HOUSEHOLD_ID,
    "name": "Feeder",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 60, "hub_rssi": 65},
        "online": True,
    },
}

MOCK_FELAQUA = {
    "id": 31337,
    "product_id": 8,
    "household_id": HOUSEHOLD_ID,
    "name": "Felaqua",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "signal": {"device_rssi": 70, "hub_rssi": 65},
        "online": True,
    },
}

MOCK_CAT_FLAP = {
    "id": 13579,
    "product_id": 6,
    "household_id": HOUSEHOLD_ID,
    "name": "Cat Flap",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 65, "hub_rssi": 64},
        "online": True,
    },
    # id: tag ID (matches pet's tag_id), profile: 3 = indoor only (HA switch ON)
    "tags": [
        {"id": 246801, "profile": 3},
    ],
}

MOCK_PET_FLAP = {
    "id": 13576,
    "product_id": 3,
    "household_id": HOUSEHOLD_ID,
    "name": "Pet Flap",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 70, "hub_rssi": 65},
        "online": True,
    },
    # id: tag ID (matches pet's tag_id), profile: 2 = outdoor (HA switch OFF)
    "tags": [
        {"id": 246801, "profile": 2},
    ],
}

MOCK_PET = {
    "id": 24680,
    "tag_id": 246801,  # Tag ID used to match against flap tags
    "household_id": HOUSEHOLD_ID,
    "name": "Pet",
    "position": {"since": "2020-08-23T23:10:50", "where": 1},
    "status": {},
}

MOCK_API_DATA = {
    "devices": [MOCK_HUB, MOCK_CAT_FLAP, MOCK_PET_FLAP, MOCK_FEEDER, MOCK_FELAQUA],
    "pets": [MOCK_PET],
}


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    surepetcare_mock: AsyncMock,
) -> SurePetcareDataCoordinator:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][config_entry.entry_id]
