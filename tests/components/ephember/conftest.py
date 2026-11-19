"""Fixtures for the EPH Controls Ember tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ephember.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import MOCK_PASSWORD, MOCK_USER_ID, MOCK_USERNAME


def _zone(
    zoneid: str, name: str, device_type: int, points: dict[int, int]
) -> dict[str, Any]:
    return {
        "zoneid": zoneid,
        "name": name,
        "deviceType": device_type,
        "pointDataList": [
            {"pointIndex": index, "value": str(value)}
            for index, value in points.items()
        ],
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for an EPH Ember account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        unique_id=MOCK_USER_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Skip setting up the config entry."""
    with patch(
        "homeassistant.components.ephember.async_setup_entry", return_value=None
    ):
        yield


@pytest.fixture
def mock_ember() -> Generator[MagicMock]:
    """Mock the EphEmber client used by the integration and the config flow."""
    with (
        patch(
            "homeassistant.components.ephember.EphEmber", autospec=True
        ) as mock_class,
        patch("homeassistant.components.ephember.config_flow.EphEmber", new=mock_class),
    ):
        ember = mock_class.return_value
        # Point 5 current temp, 6 target temp, 7 mode, 10 boiler state
        homes = [
            {
                "zones": [
                    _zone("zone1", "Radiators", 2, {5: 200, 6: 205, 7: 2, 10: 2}),
                    _zone("zone2", "Hot Water", 4, {5: 250, 6: 600, 7: 3, 10: 1}),
                ]
            }
        ]
        ember.get_zones.return_value = homes
        ember.get_zone.side_effect = lambda zoneid: next(
            zone for zone in homes[0]["zones"] if zone["zoneid"] == zoneid
        )
        ember.messenging_credentials.return_value = {
            "user_id": MOCK_USER_ID,
            "token": "token",
        }
        yield ember


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ember: MagicMock
) -> MockConfigEntry:
    """Set up the integration from a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
