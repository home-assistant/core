"""Test the ISEO Argo BLE credential sensors."""

from unittest.mock import MagicMock, patch

from iseo_argo_ble import USER_TYPE_RFID, IseoAuthError, IseoConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.iseo_argo_ble.const import (
    ATTR_ENABLED,
    DOMAIN,
    SERVICE_DELETE_CREDENTIAL,
    SERVICE_SET_CREDENTIAL_ENABLED,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import MOCK_VALIDITY

from tests.common import MockConfigEntry, snapshot_platform

ALICE_ENTITY_ID = "binary_sensor.iseo_lock_alice_card"
BOB_ENTITY_ID = "binary_sensor.iseo_lock_bob_pin"


async def _set_enabled(hass: HomeAssistant, entity_id: str, enabled: bool) -> None:
    """Call the set credential enabled action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CREDENTIAL_ENABLED,
        {ATTR_ENTITY_ID: entity_id, ATTR_ENABLED: enabled},
        blocking=True,
    )


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_admin_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test a sensor is created per credential, bar the Home Assistant ones."""
    with patch(
        "homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_admin_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_admin_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_no_sensors_without_admin_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test an entry set up without user management creates no sensors."""
    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    mock_iseo_client.read_users.assert_not_called()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_suspend_credential(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test suspending writes to the lock and updates the sensor."""
    await setup_integration(hass, mock_admin_config_entry)

    await _set_enabled(hass, ALICE_ENTITY_ID, False)

    mock_iseo_client.set_user_disabled.assert_called_once_with(
        uuid_hex="1111111111111111111111111111aaaa",
        user_type=USER_TYPE_RFID,
        disabled=True,
        validity=None,
    )
    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_OFF
    # The new state is applied to the cached list rather than re-read.
    mock_iseo_client.read_users.assert_called_once()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_restore_credential_puts_its_window_back(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test restoring hands the lock the window the credential started with.

    Suspending overwrites it, so restoring without it would turn a credential
    that was valid for one weekend into one valid forever.
    """
    await setup_integration(hass, mock_admin_config_entry)

    await _set_enabled(hass, ALICE_ENTITY_ID, False)
    await _set_enabled(hass, ALICE_ENTITY_ID, True)

    assert mock_iseo_client.set_user_disabled.await_args.kwargs == {
        "uuid_hex": "1111111111111111111111111111aaaa",
        "user_type": USER_TYPE_RFID,
        "disabled": False,
        "validity": MOCK_VALIDITY,
    }
    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_restore_refuses_when_the_window_is_unknown(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a credential suspended before setup is not restored blindly.

    Only the expired sentinel was ever read, so restoring would have to guess,
    and guessing "no restriction" grants more access than it ever had.
    """
    await setup_integration(hass, mock_admin_config_entry)
    assert hass.states.get(BOB_ENTITY_ID).state == STATE_OFF

    with pytest.raises(ServiceValidationError):
        await _set_enabled(hass, BOB_ENTITY_ID, True)

    mock_iseo_client.set_user_disabled.assert_not_called()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_update_entity_does_not_reach_the_lock(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the generic update action does not re-read the credential list.

    Repeating that admin read is what faults the lock's firmware, so asking for
    a refresh has to stay inert however it is asked for.
    """
    await setup_integration(hass, mock_admin_config_entry)
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    mock_iseo_client.read_users.reset_mock()

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ALICE_ENTITY_ID},
        blocking=True,
    )

    mock_iseo_client.read_users.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [IseoAuthError("rejected"), IseoConnectionError("no link"), TimeoutError],
)
@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_set_credential_enabled_error(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    error: Exception,
) -> None:
    """Test a failed write is reported and leaves the sensor alone."""
    await setup_integration(hass, mock_admin_config_entry)
    mock_iseo_client.set_user_disabled.side_effect = error

    with pytest.raises(HomeAssistantError):
        await _set_enabled(hass, ALICE_ENTITY_ID, False)

    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_set_credential_enabled_when_gone_from_the_lock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a credential removed in the Argo app is reported, not leaked.

    The library raises ValueError when the cached credential is no longer on
    the lock, which would otherwise surface as an unhandled error.
    """
    await setup_integration(hass, mock_admin_config_entry)
    mock_iseo_client.set_user_disabled.side_effect = ValueError("not found on lock")

    with pytest.raises(ServiceValidationError):
        await _set_enabled(hass, ALICE_ENTITY_ID, False)

    # The stale credential is dropped rather than left showing a state the
    # lock does not have.
    assert entity_registry.async_get(ALICE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_settle_is_kept_when_a_write_fails(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock still gets its settle time after a failed write."""
    await setup_integration(hass, mock_admin_config_entry)
    mock_iseo_client.set_user_disabled.side_effect = IseoConnectionError("no link")

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.binary_sensor.asyncio.sleep"
        ) as mock_sleep,
        pytest.raises(HomeAssistantError),
    ):
        await _set_enabled(hass, ALICE_ENTITY_ID, False)

    mock_sleep.assert_awaited_once()


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_set_credential_enabled_without_ble_device(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test the action reports an error while the lock is out of range."""
    await setup_integration(hass, mock_admin_config_entry)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.binary_sensor.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _set_enabled(hass, ALICE_ENTITY_ID, False)


async def _delete_credential(hass: HomeAssistant, entity_id: str) -> None:
    """Call the delete credential action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_CREDENTIAL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_delete_credential(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test deleting a credential erases it and drops the sensor."""
    await setup_integration(hass, mock_admin_config_entry)
    assert entity_registry.async_get(ALICE_ENTITY_ID) is not None

    await _delete_credential(hass, ALICE_ENTITY_ID)

    mock_iseo_client.erase_user_by_uuid.assert_called_once_with(
        uuid_bytes=bytes.fromhex("1111111111111111111111111111aaaa"),
        user_type=USER_TYPE_RFID,
        subtype=None,
    )
    assert hass.states.get(ALICE_ENTITY_ID) is None
    assert entity_registry.async_get(ALICE_ENTITY_ID) is None
    # The other credentials are untouched.
    assert hass.states.get(BOB_ENTITY_ID) is not None


@pytest.mark.parametrize(
    "error",
    [IseoAuthError("rejected"), IseoConnectionError("no link"), TimeoutError],
)
@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_delete_credential_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    error: Exception,
) -> None:
    """Test a failed delete is reported and keeps the sensor."""
    await setup_integration(hass, mock_admin_config_entry)
    mock_iseo_client.erase_user_by_uuid.side_effect = error

    with pytest.raises(HomeAssistantError):
        await _delete_credential(hass, ALICE_ENTITY_ID)

    assert entity_registry.async_get(ALICE_ENTITY_ID) is not None
    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_credential_removed_from_lock(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a sensor goes unavailable once the lock drops its credential."""
    await setup_integration(hass, mock_admin_config_entry)
    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON

    coordinator = mock_admin_config_entry.runtime_data.user_coordinator
    coordinator.async_set_updated_data(
        [user for user in coordinator.data if user.name != "Alice"]
    )
    await hass.async_block_till_done()

    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_UNAVAILABLE
