"""Tests for the Alexa Devices coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_DEVICE_1, TEST_DEVICE_1_SN, TEST_DEVICE_2, TEST_DEVICE_2_SN

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_stale_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator data update removes stale Alexa devices."""

    entity_id_0 = "binary_sensor.echo_test_connectivity"
    entity_id_1 = "binary_sensor.echo_test_2_connectivity"

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: TEST_DEVICE_1,
        TEST_DEVICE_2_SN: TEST_DEVICE_2,
    }

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_ON
    assert (state := hass.states.get(entity_id_1))
    assert state.state == STATE_ON

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: TEST_DEVICE_1,
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_ON

    # Entity is removed
    assert not hass.states.get(entity_id_1)
