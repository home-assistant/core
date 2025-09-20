"""Tests for the Alexa Devices coordinator."""

from unittest.mock import AsyncMock

from aioamazondevices.api import AmazonDevice, AmazonDeviceSensor
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_DEVICE, TEST_SERIAL_NUMBER

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
        TEST_SERIAL_NUMBER: TEST_DEVICE,
        "echo_test_2_serial_number_2": AmazonDevice(
            account_name="Echo Test 2",
            capabilities=["AUDIO_PLAYER", "MICROPHONE"],
            device_family="mine",
            device_type="echo",
            device_owner_customer_id="amazon_ower_id",
            device_cluster_members=["echo_test_2_serial_number_2"],
            online=True,
            serial_number="echo_test_2_serial_number_2",
            software_version="echo_test_2_software_version",
            do_not_disturb=False,
            response_style=None,
            bluetooth_state=True,
            entity_id="11111111-2222-3333-4444-555555555555",
            appliance_id="G1234567890123456789012345678A",
            sensors={
                "temperature": AmazonDeviceSensor(
                    name="temperature", value="22.5", scale="CELSIUS"
                )
            },
        ),
    }

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_ON
    assert (state := hass.states.get(entity_id_1))
    assert state.state == STATE_ON

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_SERIAL_NUMBER: TEST_DEVICE,
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id_0))
    assert state.state == STATE_ON

    # Entity is removed
    assert not hass.states.get(entity_id_1)
