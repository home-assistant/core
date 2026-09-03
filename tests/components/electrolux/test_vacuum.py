"""Vacuum tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_COMMAND, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.VACUUM]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_vacuum(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the vacuum."""
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
        # 700series RVC command tests
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "max_power"},
            [{"vacuumMode": "maxPower"}],
        ),
        # cybele RVC command tests
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "max"},
            [{"vacuumMode": "max"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                },
            },
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": "mocked-map-id",
                    "type": 0,
                    "roomInfo": [],
                }
            ],
        ),
        # gordias RVC command tests
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                },
            },
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": "mocked-map-id",
                    "type": 1,
                    "roomInfo": [],
                }
            ],
        ),
        # pure i9 RVC command tests
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_START,
            {},
            [{"CleaningCommand": "play"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {"robotStatus": 2},
            SERVICE_START,
            {},
            [{"CleaningCommand": "play"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"CleaningCommand": "stop"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"CleaningCommand": "pause"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"CleaningCommand": "home"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "silent"},
            [{"powerMode": 1}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "smart"},
            [{"powerMode": 2}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "power"},
            [{"powerMode": 3}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                    "zone_ids": ["mocked-zone-id"],
                    "power_mode": 3,
                },
            },
            [
                {
                    "CustomPlay": {
                        "persistentMapId": "mocked-map-id",
                        "zones": [{"zoneId": "mocked-zone-id", "powerMode": 3}],
                    }
                }
            ],
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
    """Test vacuum commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
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
        "commands",
    ),
    [
        # non-model specific error tests
        # 700series RVC command tests
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "700series_vacuum",
            "vacuum.700series_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "max_power"},
            [{"vacuumMode": "maxPower"}],
        ),
        # cybele RVC command tests
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "max"},
            [{"vacuumMode": "max"}],
        ),
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                },
            },
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": "mocked-map-id",
                    "type": 0,
                    "roomInfo": [],
                }
            ],
        ),
        # gordias RVC command tests
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_START,
            {},
            [{"cleaningCommand": "startGlobalClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {"state": "paused"},
            SERVICE_START,
            {},
            [{"cleaningCommand": "resumeClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"cleaningCommand": "stopClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"cleaningCommand": "pauseClean"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"cleaningCommand": "startGoToCharger"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "energy_saving"},
            [{"vacuumMode": "energySaving"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "quiet"},
            [{"vacuumMode": "quiet"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "standard"},
            [{"vacuumMode": "standard"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "powerful"},
            [{"vacuumMode": "powerful"}],
        ),
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                },
            },
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": "mocked-map-id",
                    "type": 1,
                    "roomInfo": [],
                }
            ],
        ),
        # pure i9 RVC command tests
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_START,
            {},
            [{"CleaningCommand": "play"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {"robotStatus": 2},
            SERVICE_START,
            {},
            [{"CleaningCommand": "play"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_STOP,
            {},
            [{"CleaningCommand": "stop"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_PAUSE,
            {},
            [{"CleaningCommand": "pause"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_RETURN_TO_BASE,
            {},
            [{"CleaningCommand": "home"}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "silent"},
            [{"powerMode": 1}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "smart"},
            [{"powerMode": 2}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "power"},
            [{"powerMode": 3}],
        ),
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            {},
            SERVICE_SEND_COMMAND,
            {
                ATTR_COMMAND: "clean_zones",
                ATTR_PARAMS: {
                    "map_id": "mocked-map-id",
                    "zone_ids": ["mocked-zone-id"],
                    "power_mode": 3,
                },
            },
            [
                {
                    "CustomPlay": {
                        "persistentMapId": "mocked-map-id",
                        "zones": [{"zoneId": "mocked-zone-id", "powerMode": 3}],
                    }
                }
            ],
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
    commands: list[dict[str, Any]],
) -> None:
    """Test vacuum commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]
