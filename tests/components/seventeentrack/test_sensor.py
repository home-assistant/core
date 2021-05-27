"""Tests for SpeedTest sensors."""
from unittest.mock import AsyncMock

from py17track.package import Package

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.seventeentrack.const import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry

SUMMARY = {
    "Not Found": 0,
    "In Transit": 1,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 1,
    "Delivered": 0,
    "Returned": 0,
}

PACKAGES = [
    Package(
        "456",
        206,
        "friendly name 1",
        "info text 1",
        "location 1",
        "2020-08-10 10:32",
    )
]


async def test_seventeentrack_sensors(hass: HomeAssistant, mock_api) -> None:
    """Test sensors created for seventeentrack integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    mock_api.return_value.packages = AsyncMock(return_value=PACKAGES)
    mock_api.return_value.summary = AsyncMock(return_value=SUMMARY)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == len(SUMMARY) + 1

    for sensor_type, qty in SUMMARY.items():
        sensor = hass.states.get(
            f"sensor.{MOCK_CONFIG[CONF_NAME]}_packages_{slugify(sensor_type)}"
        )
        assert sensor.state == str(qty)

    assert hass.states.get(f"sensor.{MOCK_CONFIG[CONF_NAME]}_all_packages").state == "1"
