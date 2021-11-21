"""Common fixutres with default mocks as well as common test helper methods."""
from unittest.mock import patch

import pytest
import tesla_wall_connector

from homeassistant.components.tesla_wall_connector.const import (
    CONF_SCAN_INTERVAL_CHARGING,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_wall_connector_version():
    """Fixture to patch mydevolo into a desired state."""

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=get_default_version_data(),
    ):
        yield


def get_default_version_data():
    """Return default version data object for a wall connector."""
    return tesla_wall_connector.wall_connector.Version(
        {
            "serial_number": "abc123",
            "part_number": "part_123",
            "firmware_version": "1.2.3",
        }
    )


async def create_wall_connector_entry(
    hass: HomeAssistant, side_effect=None
) -> MockConfigEntry:
    """Create a wall connector entry in hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        options={CONF_SCAN_INTERVAL: 30, CONF_SCAN_INTERVAL_CHARGING: 5},
    )

    entry.add_to_hass(hass)

    # We need to return vitals with a contactor_closed attribute
    # Since that is used to determine the update scan interval
    fake_vitals = tesla_wall_connector.wall_connector.Vitals(
        {
            "contactor_closed": "false",
        }
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=get_default_version_data(),
        side_effect=side_effect,
    ), patch(
        "tesla_wall_connector.WallConnector.async_get_vitals",
        return_value=fake_vitals,
        side_effect=side_effect,
    ), patch(
        "tesla_wall_connector.WallConnector.async_get_lifetime",
        return_value=None,
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
