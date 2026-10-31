"""Test Satel Integra switch."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from satel_integra import (
    SatelCommandRejectedError,
    SatelCommandResult,
    SatelNoResponseError,
    SatelResultCode,
)
from satel_integra.commands import SatelWriteCommand
from satel_integra.exceptions import SatelCommandExpiredError, SatelNotConnectedError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CODE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    MOCK_CODE,
    MOCK_ENTRY_ID,
    get_output_changed_callback,
    setup_integration,
    trigger_connection_status_update,
)


@pytest.fixture(autouse=True)
async def switches_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("mock_satel")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test switch correctly being set up."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    await snapshot_platform(hass, entity_registry, snapshot, MOCK_ENTRY_ID)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890_switch_1"), mock_config_entry_with_subentries.entry_id
    )

    assert device_entry == snapshot(name="device")


@pytest.mark.parametrize(
    ("output_state", "expected_state"),
    [
        (None, STATE_UNKNOWN),
        (False, STATE_OFF),
        (True, STATE_ON),
    ],
)
async def test_switch_initial_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    output_state: bool | None,
    expected_state: str,
) -> None:
    """Test switch has a correct initial state after initialization."""

    # Instantly call callback to ensure we have initial data set
    async def mock_start(**_: object) -> None:
        mock_satel.state.outputs[1].active = output_state
        get_output_changed_callback(mock_satel)()

    mock_satel.start = AsyncMock(side_effect=mock_start)

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == expected_state


async def test_switch_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    output_update_method = get_output_changed_callback(mock_satel)

    mock_satel.state.outputs[1].active = True
    output_update_method()
    assert hass.states.get("switch.switchable_output").state == STATE_ON

    mock_satel.state.outputs[1].active = False
    output_update_method()
    assert hass.states.get("switch.switchable_output").state == STATE_OFF


async def test_switch_change_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Test turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )

    assert hass.states.get("switch.switchable_output").state == STATE_ON
    mock_satel.set_output.assert_awaited_once_with(
        MOCK_CODE, 1, True, wait_for_result=True
    )

    mock_satel.set_output.reset_mock()

    # Test turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )

    assert hass.states.get("switch.switchable_output").state == STATE_OFF
    mock_satel.set_output.assert_awaited_once_with(
        MOCK_CODE, 1, False, wait_for_result=True
    )


@pytest.mark.parametrize(
    ("result_code", "translation_key"),
    [
        (
            SatelResultCode.USER_CODE_NOT_FOUND,
            "command_invalid_access_code",
        ),
        (SatelResultCode.NO_ACCESS, "command_no_access"),
    ],
)
async def test_switch_command_validation_error(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    result_code: SatelResultCode,
    translation_key: str,
) -> None:
    """Test switch actions report validation errors."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    mock_satel.set_output.side_effect = SatelCommandRejectedError(
        SatelWriteCommand.OUTPUTS_ON,
        SatelCommandResult(result_code),
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.switchable_output"},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    state = hass.states.get("switch.switchable_output")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("exception", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            SatelCommandRejectedError(
                SatelWriteCommand.OUTPUTS_ON,
                SatelCommandResult(0x8A),
            ),
            "command_rejected",
            {"result_code": "0x8A"},
            id="rejected",
        ),
        pytest.param(
            SatelNoResponseError(),
            "command_outcome_unknown",
            None,
            id="outcome-unknown",
        ),
        pytest.param(
            SatelCommandExpiredError(),
            "command_not_sent",
            None,
            id="expired",
        ),
        pytest.param(
            SatelNotConnectedError(),
            "command_not_sent",
            None,
            id="not-connected",
        ),
    ],
)
async def test_switch_command_error(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    exception: Exception,
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test switch actions report command errors."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    mock_satel.set_output.side_effect = exception

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.switchable_output"},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert type(err.value) is HomeAssistantError
    assert err.value.translation_placeholders == translation_placeholders
    state = hass.states.get("switch.switchable_output")
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_last_reported(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switches update last_reported if same state is reported."""
    events = async_capture_events(hass, "state_changed")
    await setup_integration(hass, mock_config_entry_with_subentries)

    first_reported = hass.states.get("switch.switchable_output").last_reported
    assert first_reported is not None
    # Initial state change event
    assert len(events) == 1

    freezer.tick(1)
    async_fire_time_changed(hass)

    # Run callbacks with same payload
    output_update_method = get_output_changed_callback(mock_satel)
    output_update_method()

    assert first_reported != hass.states.get("switch.switchable_output").last_reported
    assert len(events) == 1  # last_reported shall not fire state_changed


async def test_switch_actions_require_code(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch actions fail when access code is missing."""

    await setup_integration(hass, mock_config_entry_with_subentries)

    hass.config_entries.async_update_entry(
        mock_config_entry_with_subentries, options={CONF_CODE: None}
    )
    await hass.async_block_till_done()

    # Turning the device on or off should raise ServiceValidationError.
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.switchable_output"},
            blocking=True,
        )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.switchable_output"},
            blocking=True,
        )


async def test_availability(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test availability."""
    entity_id = "switch.switchable_output"

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get(entity_id).state == STATE_OFF

    await trigger_connection_status_update(hass, mock_satel, False)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await trigger_connection_status_update(hass, mock_satel, True)

    assert hass.states.get(entity_id).state == STATE_OFF
