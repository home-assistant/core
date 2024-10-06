"""Tests for the coordinator of EHEIM Digital."""

from unittest.mock import MagicMock, patch

from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.types import EheimDeviceType, LightMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def classic_led_ctrl_2_mock():
    """Mock a classicLEDcontrol device."""
    classic_led_ctrl_2_mock = MagicMock(spec=EheimDigitalClassicLEDControl)
    classic_led_ctrl_2_mock.tankconfig = [["CLASSIC_DAYLIGHT"], ["CLASSIC_DAYLIGHT"]]
    classic_led_ctrl_2_mock.mac_address = "00:00:00:00:00:02"
    classic_led_ctrl_2_mock.device_type = (
        EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    classic_led_ctrl_2_mock.name = "Mock classicLEDcontrol+e 2"
    classic_led_ctrl_2_mock.aquarium_name = "Mock Aquarium"
    classic_led_ctrl_2_mock.light_mode = LightMode.MAN_MODE
    classic_led_ctrl_2_mock.light_level = (70, 78)
    return classic_led_ctrl_2_mock


async def test_state_update_on_callback(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    classic_led_ctrl_mock: MagicMock,
) -> None:
    """Test the coordinator state update callback."""
    mock_config_entry.add_to_hass(hass)

    eheimdigital_hub_mock.return_value.devices = {
        "00:00:00:00:00:01": classic_led_ctrl_mock
    }
    eheimdigital_hub_mock.return_value.main = classic_led_ctrl_mock

    with patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.LIGHT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data._async_device_found(
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    classic_led_ctrl_mock.light_level = (20, 30)

    await mock_config_entry.runtime_data._async_receive_callback()

    assert (state := hass.states.get("light.mock_classicledcontrol_e_channel_0"))
    assert state == snapshot(name="light.mock_classicledcontrol_e_channel_0-state-2")


async def test_device_found_callback(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    classic_led_ctrl_mock: MagicMock,
    classic_led_ctrl_2_mock: MagicMock,
) -> None:
    """Test the coordinator device found callback."""
    mock_config_entry.add_to_hass(hass)

    eheimdigital_hub_mock.return_value.devices = {
        "00:00:00:00:00:01": classic_led_ctrl_mock
    }
    eheimdigital_hub_mock.return_value.main = classic_led_ctrl_mock

    with patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.LIGHT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await mock_config_entry.runtime_data._async_device_found(
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    eheimdigital_hub_mock.return_value.devices = {
        "00:00:00:00:00:01": classic_led_ctrl_mock,
        "00:00:00:00:00:02": classic_led_ctrl_2_mock,
    }

    await mock_config_entry.runtime_data._async_device_found(
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.known_devices == {
        "00:00:00:00:00:01",
        "00:00:00:00:00:02",
    }

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
