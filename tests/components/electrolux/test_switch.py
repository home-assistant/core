"""Switch tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
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
