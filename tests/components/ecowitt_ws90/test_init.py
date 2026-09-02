"""Test setting the Ecowitt WS90 entry up, and what happens when it fails."""

from datetime import timedelta

from ecowitt_ws90_modbus.testing import WS90_LIVE_EXAMPLE, WS90_UNIT_ID
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.ecowitt_ws90.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed

# The coordinator's SCAN_INTERVAL, kept in sync manually rather than imported
# so a change to it is a visible diff here, not a silent test speed-up.
SCAN_INTERVAL = timedelta(seconds=30)


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_registry_entry(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the sensor array is registered with its identity."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), init_integration.entry_id
    )

    assert device is not None
    assert device.manufacturer == "Ecowitt"
    assert device.model == "WS90"


@pytest.mark.parametrize(
    ("key", "expected_state"),
    [
        ("temperature", "26.2"),
        ("humidity", "60"),
        ("wind_direction", "150"),
        ("absolute_pressure", "1001.0"),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    key: str,
    expected_state: str,
) -> None:
    """Test the live readings decode from the example register image."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{key}"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_get_unit")
async def test_a_silent_ws90_retries_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a WS90 that doesn't answer at setup is retried, not given up on."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(WS90_UNIT_ID)
    unit.fail_requests(ModbusTimeoutError("no answer"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


class TestDeviceIdentityMismatch:
    """A gateway that now answers for a different WS90 (or no WS90 at all)."""

    @pytest.fixture
    def register_image(self) -> dict[int, int]:
        """A register image reporting a different device_id than the entry expects."""
        image = dict(WS90_LIVE_EXAMPLE)
        image[0x163] = 0x0000
        image[0x164] = 0x0001
        return image

    @pytest.mark.usefixtures("mock_get_unit")
    async def test_setup_fails_if_device_identity_changed(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test setup is rejected rather than adopting the new responder's identity."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
