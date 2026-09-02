"""Test the ISEO Argo BLE user switches."""

from unittest.mock import MagicMock, patch

from iseo_argo_ble import (
    USER_TYPE_PIN,
    USER_TYPE_RFID,
    IseoAuthError,
    IseoConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ALICE_ENTITY_ID = "switch.iseo_lock_alice_card"
BOB_ENTITY_ID = "switch.iseo_lock_bob_pin"


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_admin_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test a switch is created per lock user, bar the Home Assistant ones."""
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_admin_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_admin_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_no_switches_without_admin_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test an entry set up without user management creates no switches."""
    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)
    mock_iseo_client.read_users.assert_not_called()


@pytest.mark.parametrize(
    (
        "service",
        "entity_id",
        "expected_uuid",
        "expected_user_type",
        "expected_disabled",
    ),
    [
        pytest.param(
            SERVICE_TURN_OFF,
            ALICE_ENTITY_ID,
            "1111111111111111111111111111aaaa",
            USER_TYPE_RFID,
            True,
            id="disable",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            BOB_ENTITY_ID,
            "2222222222222222222222222222bbbb",
            USER_TYPE_PIN,
            False,
            id="enable",
        ),
    ],
)
@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_toggle_user(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    service: str,
    entity_id: str,
    expected_uuid: str,
    expected_user_type: int,
    expected_disabled: bool,
) -> None:
    """Test toggling a user writes to the lock and updates the switch."""
    await setup_integration(hass, mock_admin_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_iseo_client.set_user_disabled.assert_called_once_with(
        uuid_hex=expected_uuid,
        user_type=expected_user_type,
        disabled=expected_disabled,
    )
    assert hass.states.get(entity_id).state == (
        STATE_OFF if expected_disabled else STATE_ON
    )
    # The new state is applied to the cached list rather than re-read.
    mock_iseo_client.read_users.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [IseoAuthError("rejected"), IseoConnectionError("no link"), TimeoutError],
)
@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_toggle_user_error(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    error: Exception,
) -> None:
    """Test a failed write is reported and leaves the switch alone."""
    await setup_integration(hass, mock_admin_config_entry)
    mock_iseo_client.set_user_disabled.side_effect = error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ALICE_ENTITY_ID},
            blocking=True,
        )

    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_toggle_user_without_ble_device(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test toggling reports an error while the lock is out of range."""
    await setup_integration(hass, mock_admin_config_entry)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.switch.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ALICE_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_user_removed_from_lock(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a switch goes unavailable once the lock drops its user."""
    await setup_integration(hass, mock_admin_config_entry)
    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_ON

    coordinator = mock_admin_config_entry.runtime_data.user_coordinator
    coordinator.async_set_updated_data(
        [user for user in coordinator.data if user.name != "Alice"]
    )
    await hass.async_block_till_done()

    assert hass.states.get(ALICE_ENTITY_ID).state == STATE_UNAVAILABLE
