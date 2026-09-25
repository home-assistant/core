"""Switch tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the switch."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "appliance_state",
        "service",
        "data",
        "commands",
    ),
    [
        # child lock command tests
        (
            "peacock_hob",
            "switch.peacock_hob_child_lock",
            {},
            SERVICE_TURN_ON,
            {},
            [{"childLock": True}],
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    appliance_state: dict[str, Any],
    service: str,
    data: dict[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    """Test switch commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "appliance_state",
        "service",
        "data",
        "error_reason",
    ),
    [
        # child lock command error tests
        (
            "peacock_hob",
            "switch.peacock_hob_child_lock",
            {"remoteControl": "DISABLED"},
            SERVICE_TURN_ON,
            {},
            "remote_control_disabled",
        ),
        (
            "peacock_hob",
            "switch.peacock_hob_child_lock",
            {"childLock": True},
            SERVICE_TURN_OFF,
            {},
            "unsupported_operation",
        ),
    ],
)
async def test_command_errors(
    hass: HomeAssistant,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    appliance_state: dict[str, Any],
    service: str,
    data: dict[str, Any],
    error_reason: str,
) -> None:
    """Test switch commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id} | data,
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
            "peacock_hob",
            "switch.peacock_hob_child_lock",
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
    """Test switch commands."""

    appliances.send_command.side_effect = error

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == ha_error_reason
