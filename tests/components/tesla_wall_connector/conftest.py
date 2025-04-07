"""Common fixutres with default mocks as well as common test helper methods."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from tesla_wall_connector.wall_connector import Lifetime, Version, Vitals

from homeassistant.components.tesla_wall_connector.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_wall_connector_version():
    """Fixture to mock get_version calls to the wall connector API."""

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=get_default_version_data(),
    ):
        yield


@pytest.fixture
async def mock_wall_connector_setup():
    """Mock component setup."""
    with patch(
        "homeassistant.components.tesla_wall_connector.async_setup_entry",
        return_value=True,
    ):
        yield


def get_default_version_data():
    """Return default version data object for a wall connector."""
    return Version(
        {
            "serial_number": "abc123",
            "part_number": "part_123",
            "firmware_version": "1.2.3",
        }
    )


async def create_wall_connector_entry(
    hass: HomeAssistant, side_effect=None, vitals_data=None, lifetime_data=None
) -> MockConfigEntry:
    """Create a wall connector entry in hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )

    entry.add_to_hass(hass)

    with (
        patch(
            "tesla_wall_connector.WallConnector.async_get_version",
            return_value=get_default_version_data(),
            side_effect=side_effect,
        ),
        patch(
            "tesla_wall_connector.WallConnector.async_get_vitals",
            return_value=vitals_data,
            side_effect=side_effect,
        ),
        patch(
            "tesla_wall_connector.WallConnector.async_get_lifetime",
            return_value=lifetime_data,
            side_effect=side_effect,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def get_vitals_mock() -> Vitals:
    """Get mocked vitals object."""
    return MagicMock(auto_spec=Vitals)


def get_lifetime_mock() -> Lifetime:
    """Get mocked lifetime object."""
    return MagicMock(auto_spec=Lifetime)


@dataclass
class EntityAndExpectedValues:
    """Class for keeping entity id along with expected value for first and second data updates."""

    entity_id: str
    first_value: Any
    second_value: Any


async def _test_sensors(
    hass: HomeAssistant,
    entities_and_expected_values,
    vitals_first_update: Vitals,
    vitals_second_update: Vitals,
    lifetime_first_update: Lifetime,
    lifetime_second_update: Lifetime,
) -> None:
    """Test update of sensor values."""

    # First Update: Data is fetched when the integration is initialized
    await create_wall_connector_entry(
        hass, vitals_data=vitals_first_update, lifetime_data=lifetime_first_update
    )

    # Verify expected vs actual values of first update
    for entity in entities_and_expected_values:
        state = hass.states.get(entity.entity_id)
        assert state, f"Unable to get state of {entity.entity_id}"
        assert state.state == entity.first_value, (
            f"First update: {entity.entity_id} is expected to have state {entity.first_value} but has {state.state}"
        )

    # Simulate second data update
    with (
        patch(
            "tesla_wall_connector.WallConnector.async_get_vitals",
            return_value=vitals_second_update,
        ),
        patch(
            "tesla_wall_connector.WallConnector.async_get_lifetime",
            return_value=lifetime_second_update,
        ),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        )
        await hass.async_block_till_done()

    # Verify expected vs actual values of second update
    for entity in entities_and_expected_values:
        state = hass.states.get(entity.entity_id)
        assert state.state == entity.second_value, (
            f"Second update: {entity.entity_id} is expected to have state {entity.second_value} but has {state.state}"
        )
