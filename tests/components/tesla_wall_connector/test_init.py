"""Test the Tesla Wall Connector config flow."""
from unittest.mock import patch

import tesla_wall_connector
from tesla_wall_connector import wall_connector

from homeassistant.components.tesla_wall_connector.const import (
    CONF_SCAN_INTERVAL_CHARGING,
    DOMAIN,
    WALLCONNECTOR_CLIENT,
    WALLCONNECTOR_DATA_UPDATE_COORDINATOR,
    WALLCONNECTOR_SERIAL_NUMBER,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


async def test_init_success(hass: HomeAssistant) -> None:
    """Test setup and that we get the device info, including firmware version."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        options={CONF_SCAN_INTERVAL: 30, CONF_SCAN_INTERVAL_CHARGING: 5},
    )

    entry.add_to_hass(hass)

    fake_version_obj = tesla_wall_connector.wall_connector.Version(
        {
            "serial_number": "abc123",
            "part_number": "part_123",
            "firmware_version": "1.2.3",
        }
    )

    # We need to return vitals with a contactor_closed attribute
    # Since that is used to determine the update scan interval
    fake_vitals = tesla_wall_connector.wall_connector.Vitals(
        {
            "contactor_closed": "false",
        }
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ), patch(
        "tesla_wall_connector.WallConnector.async_get_vitals",
        return_value=fake_vitals,
    ) as vitals_mock, patch(
        "tesla_wall_connector.WallConnector.async_get_lifetime",
        return_value=None,
    ) as lifetime_mock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN][entry.entry_id] is not None
    assert isinstance(
        hass.data[DOMAIN][entry.entry_id][WALLCONNECTOR_CLIENT],
        wall_connector.WallConnector,
    )
    assert hass.data[DOMAIN][entry.entry_id][WALLCONNECTOR_SERIAL_NUMBER] == "abc123"
    assert isinstance(
        hass.data[DOMAIN][entry.entry_id][WALLCONNECTOR_DATA_UPDATE_COORDINATOR],
        DataUpdateCoordinator,
    )

    # Verify that the DataUpdateCoordinator fetches the initial data
    assert vitals_mock.call_count == 1
    assert lifetime_mock.call_count == 1
