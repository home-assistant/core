"""Tests for SpeedTest sensors."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.seventeentrack.const import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from . import ARCHIVED_PACKAGES, ARCHIVED_SUMMARY, PACKAGES, SUMMARY, TOTAL_SUMMARY
from .test_config_flow import MOCK_CONFIG, MOCK_OPTIONS

from tests.common import MockConfigEntry


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
        if sensor := hass.states.get(
            f"sensor.{MOCK_CONFIG[CONF_NAME]}_packages_{slugify(sensor_type)}"
        ):
            assert sensor.state == str(qty)

    if all_packages_sensor := hass.states.get("sensor.seventeentrack_all_packages"):
        assert all_packages_sensor.state == "2"
