"""Button tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the button."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "state_property",
        "state_value",
        "command_payload",
    ),
    [
        # Tumble Dryer Start/Pause/Resume/Stop buttons
        (
            "tumble_dryer",
            "button.dryer_appliance_start",
            "applianceState",
            "READY_TO_START",
            {"executeCommand": "START"},
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_pause",
            "applianceState",
            "RUNNING",
            {"executeCommand": "PAUSE"},
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_resume",
            "applianceState",
            "PAUSED",
            {"executeCommand": "RESUME"},
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_stop",
            "applianceState",
            "PAUSED",
            {"executeCommand": "STOPRESET"},
        ),
        # Oven Start/Stop buttons
        (
            "fenix_oven",
            "button.fenix_appliance_start",
            "applianceState",
            "READY_TO_START",
            {"executeCommand": "START"},
        ),
        (
            "fenix_oven",
            "button.fenix_appliance_stop",
            "applianceState",
            "RUNNING",
            {"executeCommand": "STOPRESET"},
        ),
    ],
)
async def test_press(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    appliance_fixture: str,
    entity_id: str,
    state_property: str,
    state_value: Any,
    command_payload: dict[str, Any],
) -> None:
    """Test states of the number entity."""

    appliance_id = get_appliance_id(appliance_fixture)

    appliance_state = await appliances.get_appliance_state(appliance_id)
    appliance_state.properties["reported"][state_property] = state_value

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = appliance_state

    await setup_integration(hass, mock_config_entry)

    appliance_id = get_appliance_id(appliance_fixture)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    appliances.send_command.assert_called_once_with(
        appliance_id,
        command_payload,
    )


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "state_property",
        "state_value",
        "error_reason",
    ),
    [
        (
            "tumble_dryer",
            "button.dryer_appliance_start",
            "remoteControl",
            "DISABLED",
            "remote_control_disabled",
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_start",
            "applianceState",
            "RUNNING",
            "unsupported_state_for_command",
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_pause",
            "applianceState",
            "READY_TO_START",
            "unsupported_state_for_command",
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_resume",
            "applianceState",
            "RUNNING",
            "unsupported_state_for_command",
        ),
        (
            "tumble_dryer",
            "button.dryer_appliance_stop",
            "applianceState",
            "RUNNING",
            "unsupported_state_for_command",
        ),
        # Oven Start/Stop buttons
        (
            "fenix_oven",
            "button.fenix_appliance_start",
            "applianceState",
            "RUNNING",
            "unsupported_state_for_command",
        ),
        (
            "fenix_oven",
            "button.fenix_appliance_stop",
            "applianceState",
            "READY_TO_START",
            "unsupported_state_for_command",
        ),
    ],
)
async def test_press_error(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    appliance_fixture: str,
    entity_id: str,
    state_property: str,
    state_value: Any,
    error_reason: str,
) -> None:
    """Test states of the number entity."""

    appliance_id = get_appliance_id(appliance_fixture)

    appliance_state = await appliances.get_appliance_state(appliance_id)
    appliance_state.properties["reported"][state_property] = state_value

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = appliance_state

    await setup_integration(hass, mock_config_entry)

    appliance_id = get_appliance_id(appliance_fixture)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == error_reason
    appliances.send_command.assert_not_called()


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
    ),
    [
        # child lock command error tests
        (
            "tumble_dryer",
            "button.dryer_appliance_start",
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "error",
        "ha_error_reason",
    ),
    [
        # child lock command error tests
        (
            ApplianceClientException(status=401),
            "authorization_failed",
        ),
        (
            ApplianceClientException(status=403),
            "authorization_failed",
        ),
        (
            ApplianceClientException(status=406),
            "command_validation_failed",
        ),
        (
            ApplianceClientException(status=500),
            "generic_error",
        ),
        (
            ApplianceClientException(),
            "generic_error",
        ),
    ],
)
async def test_command_backend_errors(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    error: Exception,
    ha_error_reason: str,
) -> None:
    """Test generic (non-entity specific) command backend errors."""

    appliances.send_command.side_effect = error

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == ha_error_reason
