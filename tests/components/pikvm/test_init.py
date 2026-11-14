"""Tests for the PiKVM integration setup."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pikvm_aio import PiKVMAuthenticationError, PiKVMConnectionError, PiKVMDeviceError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pikvm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL

CPU_TEMPERATURE_ENTITY_ID = "sensor.pikvm_cpu_temperature"
CPU_TEMPERATURE = "52.582"


async def test_load_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test loading and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            PiKVMConnectionError, ConfigEntryState.SETUP_RETRY, id="cannot_connect"
        ),
        pytest.param(PiKVMDeviceError, ConfigEntryState.SETUP_RETRY, id="device_error"),
        pytest.param(
            PiKVMAuthenticationError, ConfigEntryState.SETUP_ERROR, id="invalid_auth"
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pikvm_client: MagicMock,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors are mapped to the right config entry state."""
    mock_pikvm_client.get_info.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_device_info(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the PiKVM device is registered with its hardware details."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), init_integration.entry_id
    )
    assert device == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_entities_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_pikvm_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when polling fails, then recover."""
    assert hass.states.get(CPU_TEMPERATURE_ENTITY_ID).state == CPU_TEMPERATURE

    mock_pikvm_client.get_info.side_effect = PiKVMConnectionError
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CPU_TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_pikvm_client.get_info.side_effect = None
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CPU_TEMPERATURE_ENTITY_ID).state == CPU_TEMPERATURE
