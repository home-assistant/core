"""Fan tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.FAN]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_fan(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the fan."""
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
        # turn on/off command tests
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {},
            SERVICE_TURN_ON,
            {},
            [{"Workmode": "Manual"}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {},
            SERVICE_TURN_OFF,
            {},
            [{"Workmode": "PowerOff"}],
        ),
        # set percentage command tests
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 0},
            [{"Workmode": "PowerOff"}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 33},
            [{"Fanspeed": 1}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 66},
            [{"Fanspeed": 2}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 100},
            [{"Fanspeed": 3}],
        ),
        # set preset mode command tests
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "manual"},
            [{"Workmode": "Manual"}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "quiet"},
            [{"Workmode": "Quiet"}],
        ),
        (
            "electrolux_air_purifier",
            "fan.air_purifier_fan",
            {"Workmode": "Manual"},
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "smart"},
            [{"Workmode": "Smart"}],
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
    """Test fan commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]
