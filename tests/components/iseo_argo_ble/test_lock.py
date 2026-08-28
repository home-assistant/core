"""Test the ISEO Argo BLE lock entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iseo_argo_ble.const import CONF_ENABLE_POLLING, DOMAIN
from homeassistant.components.iseo_argo_ble.lock import (
    _AVAILABILITY_CHECK_INTERVAL,
    _POLL_INTERVAL,
    _UNAVAILABLE_AFTER,
)
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import iseo_advertisement, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info_bleak

ENTITY_ID = "lock.iseo_lock"


def _lock_state(door_closed: bool | None) -> MagicMock:
    """Return a lock state reporting the given door status."""
    return MagicMock(door_closed=door_closed, firmware_info="FW:  1.2.3")


async def _advertise(hass: HomeAssistant, door_closed: bool) -> None:
    """Feed the integration an advertisement with the given door status."""
    inject_bluetooth_service_info_bleak(hass, iseo_advertisement(door_closed))
    await hass.async_block_till_done()


async def _unlock(hass: HomeAssistant) -> None:
    """Call the unlock action on the lock."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test the lock entity and its device."""
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_iseo_client", "mock_derive_private_key", "mock_ble_device"
)
async def test_firmware_version_is_reported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the firmware version read from the lock lands on the device."""
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.2.3"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_state_follows_door_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the reported state follows the door status the lock advertises."""
    await setup_integration(hass, mock_config_entry)

    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    await _advertise(hass, door_closed=False)
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED

    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    # Advertisements alone must never make the integration connect.
    mock_iseo_client.read_state.assert_awaited_once()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_keeps_unlocked_while_door_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test an open door is not reported as locked after unlocking."""
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    mock_iseo_client.gw_open.assert_called_once()

    # The door was opened right after the latch was released.
    await _advertise(hass, door_closed=False)
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_reports_locked_once_door_is_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock reports locked again once the door is closed."""
    await setup_integration(hass, mock_config_entry)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_assumes_locked_without_door_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a lock that never reports door status is assumed locked again."""
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.usefixtures("mock_derive_private_key")
async def test_availability_recovers_from_an_advertisement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test the lock becomes available again on the next advertisement."""
    await setup_integration(hass, mock_config_entry)

    # Out of range and never heard from, so there is nothing to connect to.
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _unlock(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Hearing it again is enough to recover.
    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    # Availability itself costs no connection: the one-off probe already ran.
    mock_iseo_client.read_state.reset_mock()
    await _advertise(hass, door_closed=True)
    mock_iseo_client.read_state.assert_not_called()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unavailable_when_lock_rejects_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock becomes unavailable when it rejects the stored identity."""
    mock_iseo_client.read_state.side_effect = IseoAuthError("rejected")
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Hearing the lock says nothing about whether it accepts our identity, so a
    # further advertisement must not make it look healthy again.
    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unavailable_when_it_stops_advertising(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock is unavailable once its advertisements stop arriving."""
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    freezer.tick(_UNAVAILABLE_AFTER + _AVAILABILITY_CHECK_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Hearing it again brings it straight back.
    await _advertise(hass, door_closed=True)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_advertisement_does_not_override_unsupported_door_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the door bit is ignored when the lock says it has no door status.

    Advertisements carry no capability flags, so the bit is meaningless on a
    lock whose capabilities say door status is unsupported.
    """
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    await _advertise(hass, door_closed=False)

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_advertisement_without_door_status_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test an advertisement carrying no door state leaves the state alone."""
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=False)
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED

    # A marker-only advertisement: no state word, so nothing to apply.
    info = iseo_advertisement(True)
    info.service_uuids.remove("0000e800-0000-1000-8000-00805f9b34fb")
    inject_bluetooth_service_info_bleak(hass, info)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key")
async def test_unlock_uses_the_last_advertised_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test unlocking still works when the manager has no device cached.

    Clearing the advertisement history to keep passive callbacks flowing also
    drops the manager's device cache, so the address lookup can come back empty
    for a lock that is advertising perfectly well.
    """
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        # No advertisement will arrive during the test; don't sit out the wait.
        patch("homeassistant.components.iseo_argo_ble.lock._ADVERTISEMENT_WAIT", 0),
    ):
        await _unlock(hass)
        await hass.async_block_till_done()

    mock_iseo_client.gw_open.assert_called_once()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_no_connection_is_made_on_a_timer_by_default(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the integration does not connect on a schedule by default.

    Advertisements carry the door state, so the single read at setup is the only
    connection the entity makes on its own.
    """
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)
    mock_iseo_client.read_state.assert_awaited_once()

    mock_iseo_client.read_state.reset_mock()
    freezer.tick(_POLL_INTERVAL * 4)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_iseo_client.read_state.assert_not_called()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_polling_option_connects_on_a_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the opt-in fallback polls locks that cannot advertise door status."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_POLLING: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_iseo_client.read_state.reset_mock()
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_iseo_client.read_state.assert_awaited()
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures(
    "mock_derive_private_key", "mock_iseo_client", "mock_ble_device"
)
async def test_lock_action_is_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test locking on demand raises, the lock re-latches on its own."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert excinfo.value.translation_key == "lock_not_supported"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_rejected_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the lock rejects the identity."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.gw_open = AsyncMock(side_effect=IseoAuthError("bad auth"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "lock_rejected_identity"
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises and marks unavailable when the connection fails."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.gw_open = AsyncMock(side_effect=IseoConnectionError("no link"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "cannot_connect"
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_without_device_in_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the lock is not advertising."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await _unlock(hass)

    assert excinfo.value.translation_key == "cannot_connect"
    mock_iseo_client.gw_open.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_polling_keeps_probing_a_lock_without_door_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the fallback keeps reading a lock that reports no door status.

    Door Status Advice can be turned on from the Argo app at any time, and that
    only becomes visible in a read.
    """
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_POLLING: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _advertise(hass, door_closed=True)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_ASSUMED_STATE] is True

    # The lock starts reporting door status; a later poll must pick it up.
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_door_opening_during_the_relock_window_is_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the door opening right after an unlock is not discarded.

    Idle advertisements can be minutes apart, so dropping this one would leave
    the entity reporting locked with the door standing open.
    """
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    await _unlock(hass)
    await _advertise(hass, door_closed=False)

    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED

    # The relock timer must not undo it either.
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_probe_retries_when_the_first_read_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a transient failure does not permanently skip the one-off read."""
    mock_iseo_client.read_state.side_effect = IseoConnectionError("busy")
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    mock_iseo_client.read_state.side_effect = None
    mock_iseo_client.read_state.reset_mock()
    await _advertise(hass, door_closed=True)

    mock_iseo_client.read_state.assert_awaited()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_probe_stops_retrying_a_rejected_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a rejected identity is not retried on every advertisement.

    It cannot recover without re-enrolling, so retrying only wakes the lock.
    """
    mock_iseo_client.read_state.side_effect = IseoAuthError("rejected")
    await setup_integration(hass, mock_config_entry)
    await _advertise(hass, door_closed=True)

    mock_iseo_client.read_state.reset_mock()
    await _advertise(hass, door_closed=True)
    await _advertise(hass, door_closed=True)

    mock_iseo_client.read_state.assert_not_called()
