"""Tests for the Tankerkoening integration."""
from __future__ import annotations

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.tankerkoenig.const import (
    CONF_FUEL_TYPES,
    CONF_STATIONS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

MOCK_USER_DATA = {
    CONF_NAME: "Home",
    CONF_API_KEY: "269534f6-xxxx-xxxx-xxxx-yyyyzzzzxxxx",
    CONF_FUEL_TYPES: ["e5"],
    CONF_LOCATION: {CONF_LATITUDE: 51.0, CONF_LONGITUDE: 13.0},
    CONF_RADIUS: 2.0,
    CONF_STATIONS: [
        "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
    ],
}
MOCK_OPTIONS = {
    CONF_SHOW_ON_MAP: True,
}

MOCK_STATION_DATA = {
    "ok": True,
    "station": {
        "id": "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
        "name": "Station ABC",
        "brand": "Station",
        "street": "Somewhere Street",
        "houseNumber": "1",
        "postCode": "01234",
        "place": "Somewhere",
        "openingTimes": [],
        "overrides": [],
        "wholeDay": True,
        "isOpen": True,
        "e5": 1.719,
        "e10": 1.659,
        "diesel": 1.659,
        "lat": 51.1,
        "lng": 13.1,
        "state": "xxXX",
    },
}
MOCK_STATION_PRICES = {
    "ok": True,
    "prices": {
        "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8": {
            "status": "open",
            "e5": 1.719,
            "e10": 1.659,
            "diesel": 1.659,
        },
    },
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    with patch(
        "homeassistant.components.tankerkoenig.coordinator.pytankerkoenig.getStationData",
        return_value=MOCK_STATION_DATA,
    ), patch(
        "homeassistant.components.tankerkoenig.coordinator.pytankerkoenig.getPriceList",
        return_value=MOCK_STATION_PRICES,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_USER_DATA,
            options=MOCK_OPTIONS,
            unique_id="mock.tankerkoenig",
            entry_id="8036b4412f2fae6bb9dbab7fe8e37f87",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
