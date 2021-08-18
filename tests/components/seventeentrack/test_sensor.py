"""Tests for SpeedTest sensors."""
from unittest.mock import AsyncMock, MagicMock

from py17track.package import Package

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.seventeentrack.const import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .test_config_flow import MOCK_CONFIG, MOCK_OPTIONS

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
        status=10,
    )
]
ARCHIVED_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 1,
    "Ready to be Picked Up": 0,
    "Undelivered": 1,
    "Delivered": 0,
    "Returned": 0,
}

ARCHIVED_PACKAGES = [
    Package(
        "410",
        206,
        "friendly name 2",
        "info text 2",
        "location 2",
        "2020-07-10 10:32",
        status=20,
    )
]

TOTAL_SUMMARY = {
    "Not Found": 0,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 0,
    "Undelivered": 2,
    "Delivered": 0,
    "Returned": 0,
}


async def test_seventeentrack_sensors(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test sensors created for seventeentrack integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS)
    entry.add_to_hass(hass)

    mock_api.return_value.packages = AsyncMock(
        side_effect=[PACKAGES, ARCHIVED_PACKAGES]
    )
    mock_api.return_value.summary = AsyncMock(side_effect=[SUMMARY, ARCHIVED_SUMMARY])

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == len(SUMMARY) + 1

    for sensor_type, qty in TOTAL_SUMMARY.items():
        sensor = hass.states.get(
            f"sensor.{MOCK_CONFIG[CONF_NAME]}_packages_{slugify(sensor_type)}"
        )
        if sensor:
            assert sensor.state == str(qty)

    all_packages_sensor = hass.states.get("sensor.seventeentrack_all_packages")
    if all_packages_sensor:
        assert all_packages_sensor.state == "2"
