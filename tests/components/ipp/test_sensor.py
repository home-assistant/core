"""Tests for the IPP sensor platform."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.ipp.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.components.ipp import init_integration, mock_connection
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the IPP sensors."""
    mock_connection(aioclient_mock)

    entry = await init_integration(hass, aioclient_mock, skip_setup=True)
    registry = er.async_get(hass)

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "cfe92100-67c4-11d4-a45f-f8d027761251_uptime",
        suggested_object_id="epson_xp_6000_series_uptime",
        disabled_by=None,
    )

    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.ipp.sensor.utcnow", return_value=test_time):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.epson_xp_6000_series")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    state = hass.states.get("sensor.epson_xp_6000_series_black_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "58"

    state = hass.states.get("sensor.epson_xp_6000_series_photo_black_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "98"

    state = hass.states.get("sensor.epson_xp_6000_series_cyan_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "91"

    state = hass.states.get("sensor.epson_xp_6000_series_yellow_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "95"

    state = hass.states.get("sensor.epson_xp_6000_series_magenta_ink")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:water"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.state == "73"

    state = hass.states.get("sensor.epson_xp_6000_series_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-10-26T15:37:00+00:00"

    entry = registry.async_get("sensor.epson_xp_6000_series_uptime")
    assert entry
    assert entry.unique_id == "cfe92100-67c4-11d4-a45f-f8d027761251_uptime"


async def test_disabled_by_default_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the disabled by default IPP sensors."""
    await init_integration(hass, aioclient_mock)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.epson_xp_6000_series_uptime")
    assert state is None

    entry = registry.async_get("sensor.epson_xp_6000_series_uptime")
    assert entry
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION


async def test_missing_entry_unique_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the unique_id of IPP sensor when printer is missing identifiers."""
    entry = await init_integration(hass, aioclient_mock, uuid=None, unique_id=None)
    registry = er.async_get(hass)

    entity = registry.async_get("sensor.epson_xp_6000_series")
    assert entity
    assert entity.unique_id == f"{entry.entry_id}_printer"
