"""Tests for the Alexa Devices coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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


async def test_coordinator_load_previous_devices_from_registry(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test coordinator preloads previous devices from registry excluding services."""
    mock_config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)},
        name="Echo Test",
        manufacturer="Amazon",
        model="Echo Dot",
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Amazon",
        model="Echo Dot",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.previous_devices == {TEST_DEVICE_1_SN}
