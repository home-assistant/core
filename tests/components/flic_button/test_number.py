"""Test the Flic Button number platform."""

from typing import Any
from unittest.mock import MagicMock

from pyflic_ble import DeviceType, FlicProtocolError, PushTwistMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flic_button.const import CONF_PUSH_TWIST_MODE
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, PERCENTAGE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

SLOT_1_ENTITY_ID = "number.flic_twist_t12345_slot_1"
SLOT_3_ENTITY_ID = "number.flic_twist_t12345_slot_3"
TWIST_POSITION_ENTITY_ID = "number.flic_twist_t12345_twist_position"
PUSH_TWIST_POSITION_ENTITY_ID = "number.flic_twist_t12345_push_twist_position"


@pytest.fixture
def platforms() -> list[Platform]:
    """Set up only the number platform."""
    return [Platform.NUMBER]


async def setup_twist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    push_twist_mode: PushTwistMode,
) -> None:
    """Set up a Flic Twist config entry with the given push twist mode."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_PUSH_TWIST_MODE: push_twist_mode}
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "mock_flic_client",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
@pytest.mark.parametrize(
    "push_twist_mode",
    [PushTwistMode.DEFAULT, PushTwistMode.CONTINUOUS, PushTwistMode.SELECTOR],
)
async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    push_twist_mode: PushTwistMode,
) -> None:
    """Test the number entities created for each push twist mode."""
    await setup_twist(hass, mock_config_entry, push_twist_mode)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_flic_client",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("device_type", [DeviceType.FLIC2, DeviceType.DUO])
async def test_no_number_entities_without_selector(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test devices without a selector do not get number entities."""
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_rotate_event_updates_own_mode_only(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a rotation event only updates the entity of the rotated mode."""
    await setup_twist(hass, mock_config_entry, PushTwistMode.SELECTOR)

    for call in mock_flic_client.register_rotate_event_callback.call_args_list:
        call.args[0](
            "rotate_clockwise", {"twist_mode_index": 2, "mode_percentage": 42.4}
        )
    await hass.async_block_till_done()

    assert hass.states.get(SLOT_3_ENTITY_ID).state == "42"
    assert hass.states.get(SLOT_1_ENTITY_ID).state == "0"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_set_value(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a position sends it to the device."""
    await setup_twist(hass, mock_config_entry, PushTwistMode.DEFAULT)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: PUSH_TWIST_POSITION_ENTITY_ID, ATTR_VALUE: 55},
        blocking=True,
    )

    mock_flic_client.async_send_update_twist_position.assert_awaited_once_with(12, 55.0)
    assert hass.states.get(PUSH_TWIST_POSITION_ENTITY_ID).state == "55.0"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_set_value_error(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failing write is reported as a translated error."""
    await setup_twist(hass, mock_config_entry, PushTwistMode.DEFAULT)
    mock_flic_client.async_send_update_twist_position.side_effect = FlicProtocolError(
        "Session not established"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: TWIST_POSITION_ENTITY_ID, ATTR_VALUE: 55},
            blocking=True,
        )

    assert err.value.translation_key == "set_position_failed"
    assert hass.states.get(TWIST_POSITION_ENTITY_ID).state == "0"


def _restore(entity_id: str, value: float) -> tuple[State, dict[str, Any]]:
    """Seed the restore cache with a stored position."""
    return (
        State(entity_id, str(value)),
        {
            "native_max_value": 100,
            "native_min_value": 0,
            "native_step": 1,
            "native_unit_of_measurement": PERCENTAGE,
            "native_value": value,
        },
    )


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_position_restored_and_sent_to_device(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the last position is restored and handed back to the device."""
    mock_restore_cache_with_extra_data(
        hass, (_restore(TWIST_POSITION_ENTITY_ID, 40.0),)
    )

    await setup_twist(hass, mock_config_entry, PushTwistMode.DEFAULT)

    assert hass.states.get(TWIST_POSITION_ENTITY_ID).state == "40.0"
    mock_flic_client.async_send_update_twist_position.assert_awaited_once_with(0, 40.0)


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_restore_keeps_position_when_device_rejects_it(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failing restore write still leaves the position restored."""
    mock_restore_cache_with_extra_data(
        hass, (_restore(TWIST_POSITION_ENTITY_ID, 40.0),)
    )
    mock_flic_client.async_send_update_twist_position.side_effect = FlicProtocolError(
        "Session not established"
    )

    await setup_twist(hass, mock_config_entry, PushTwistMode.DEFAULT)

    assert hass.states.get(TWIST_POSITION_ENTITY_ID).state == "40.0"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_position_restored_when_device_connects_later(
    hass: HomeAssistant,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a position restored while offline is sent once the session comes up."""
    mock_restore_cache_with_extra_data(
        hass, (_restore(TWIST_POSITION_ENTITY_ID, 40.0),)
    )
    mock_flic_client.state.connected = False

    await setup_twist(hass, mock_config_entry, PushTwistMode.DEFAULT)

    mock_flic_client.async_send_update_twist_position.assert_not_awaited()

    state_callbacks = [
        call.args[0] for call in mock_flic_client.register_state_callback.call_args_list
    ]
    mock_flic_client.state.connected = True
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    # A second notification before the first write lands must not queue another
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()

    mock_flic_client.async_send_update_twist_position.assert_awaited_once_with(0, 40.0)

    # A later reconnect must not overwrite what the library already resumed
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()

    mock_flic_client.async_send_update_twist_position.assert_awaited_once_with(0, 40.0)
