"""Vacuum tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_AREA,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator


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


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "expected_segments",
    ),
    [
        # cybele RVC
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            [
                {"id": "1_11", "name": "Map 1: Storage", "group": None},
                {"id": "1_12", "name": "Map 1: Kitchen", "group": None},
            ],
        ),
        # gordias RVC
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            [
                {"id": "1_11", "name": "Map 1: Storage", "group": None},
                {"id": "1_12", "name": "Map 1: Kitchen", "group": None},
            ],
        ),
        # pure i9 RVC
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            [
                {"id": "map-id-1_zone-id-1", "name": "Map 1: Bathroom", "group": None},
                {"id": "map-id-1_zone-id-3", "name": "Map 1: Kitchen", "group": None},
            ],
        ),
    ],
)
async def test_get_segments(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_segments: list[dict[str, str]],
) -> None:
    """Test vacuum get_segments service."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"segments": expected_segments}


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "commands",
    ),
    [
        # cybele RVC
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": 18,
                    "type": 0,
                    "roomInfo": [{"roomId": 42}, {"roomId": 48}],
                }
            ],
        ),
        # gordias RVC
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            [
                {
                    "mapCommand": "selectRoomsClean",
                    "mapId": 18,
                    "type": 1,
                    "roomInfo": [
                        {
                            "roomId": 42,
                            "sweepMode": 0,
                            "vacuumMode": "standard",
                            "waterPumpRate": "off",
                            "numberOfCleaningRepetitions": 1,
                        },
                        {
                            "roomId": 48,
                            "sweepMode": 0,
                            "vacuumMode": "standard",
                            "waterPumpRate": "off",
                            "numberOfCleaningRepetitions": 1,
                        },
                    ],
                }
            ],
        ),
        # pure i9 RVC
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            [
                {
                    "CustomPlay": {
                        "persistentMapId": "18",
                        "zones": [
                            {"zoneId": "42", "powerMode": 2},
                            {"zoneId": "48", "powerMode": 2},
                        ],
                    }
                }
            ],
        ),
    ],
)
async def test_clean_area(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    commands: list[dict[str, Any]],
) -> None:
    """Test vacuum commands."""

    appliance_id = get_appliance_id(appliance_fixture)

    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_id_1": ["18_42", "18_48"]},
            "last_seen_segments": [
                {"id": "18_42", "name": "Example room 1", "group": "Floor 1"},
                {"id": "18_48", "name": "Example room 2", "group": "Floor 1"},
                {"id": "19_42", "name": "Example room 1", "group": "Floor 2"},
            ],
        },
    )

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_CLEAN_AREA,
        {ATTR_ENTITY_ID: entity_id, "cleaning_area_id": ["area_id_1"]},
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "error_reason",
    ),
    [
        # cybele RVC
        (
            "cybele_vacuum",
            "vacuum.cybele_vacuum",
            "multiple_map_ids",
        ),
        # gordias RVC
        (
            "gordias_vacuum",
            "vacuum.gordias_vacuum",
            "multiple_map_ids",
        ),
        # pure i9 RVC
        (
            "purei9_vacuum",
            "vacuum.pure_i9_vacuum",
            "multiple_map_ids",
        ),
    ],
)
async def test_clean_area_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    error_reason: str,
) -> None:
    """Test vacuum commands."""

    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_id_1": ["18_42", "19_42"]},
            "last_seen_segments": [
                {"id": "18_42", "name": "Example room 1", "group": "Floor 1"},
                {"id": "18_48", "name": "Example room 2", "group": "Floor 1"},
                {"id": "19_42", "name": "Example room 1", "group": "Floor 2"},
            ],
        },
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_CLEAN_AREA,
            {ATTR_ENTITY_ID: entity_id, "cleaning_area_id": ["area_id_1"]},
            blocking=True,
        )
    assert exc_info.value.translation_key == error_reason
    appliances.send_command.assert_not_called()
