"""Humidifier tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.HUMIDIFIER]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_humidifier(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the humidifier."""
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
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {},
            SERVICE_TURN_ON,
            {},
            [{"executeCommand": "ON"}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {},
            SERVICE_TURN_OFF,
            {},
            [{"executeCommand": "OFF"}],
        ),
        # set humidity command tests
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 35},
            [{"targetHumidity": 35}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 45},
            [{"targetHumidity": 45}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 85},
            [{"targetHumidity": 85}],
        ),
        # set mode command tests
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_MODE,
            {ATTR_MODE: "AUTO"},
            [{"mode": "AUTO"}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_MODE,
            {ATTR_MODE: "CONTINUOUS"},
            [{"mode": "CONTINUOUS"}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_MODE,
            {ATTR_MODE: "DRY"},
            [{"mode": "DRY"}],
        ),
        (
            "electrolux_dehumidifier",
            "humidifier.dehumidifier",
            {"applianceState": "RUNNING"},
            SERVICE_SET_MODE,
            {ATTR_MODE: "QUIET"},
            [{"mode": "QUIET"}],
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
        HUMIDIFIER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]
