"""Test Flo by Moen binary sensor entities."""

import pytest

from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_binary_sensors(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test Flo by Moen sensors."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()

    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 2

    valve_state = hass.states.get(
        "binary_sensor.smart_water_shutoff_pending_system_alerts"
    )
    assert valve_state.state == STATE_ON
    assert valve_state.attributes.get("info") == 0
    assert valve_state.attributes.get("warning") == 2
    assert valve_state.attributes.get("critical") == 0
    assert (
        valve_state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Smart water shutoff Pending system alerts"
    )

    detector_state = hass.states.get("binary_sensor.kitchen_sink_water_detected")
    assert detector_state.state == STATE_OFF
