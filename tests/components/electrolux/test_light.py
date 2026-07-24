"""Binary sensor tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.LIGHT]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("appliance_fixture", "entity_id", "appliance_state", "data", "commands"),
    [
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 0},
            {},
            [{"lightIntensity": 70}],
        ),
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 0},
            {ATTR_BRIGHTNESS: 50},
            [{"lightIntensity": 20}],
        ),
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 70},
            {ATTR_BRIGHTNESS: 50},
            [{"lightIntensity": 20}],
        ),
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 70},
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            [{"lightColorTemperature": 42}],
        ),
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 0},
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            [{"lightIntensity": 70}, {"lightColorTemperature": 42}],
        ),
        (
            "fenix_oven",
            "light.fenix_cavity_light",
            {},
            {},
            [{"cavityLight": True}],
        ),
        (
            "supex_structured_oven",
            "light.supex_oven_upper_cavity_light",
            {},
            {},
            [{"upperOven": {"cavityLight": True}}],
        ),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    appliance_state: dict[str, Any],
    data: dict[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    """Test light turn on command."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    for state_property, state_value in appliance_state.items():
        state.properties["reported"][state_property] = state_value

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]


@pytest.mark.parametrize(
    ("appliance_fixture", "entity_id", "appliance_state", "data", "commands"),
    [
        (
            "hood",
            "light.ceiling_hood_light",
            {"lightIntensity": 70},
            {},
            [{"lightIntensity": 0}],
        ),
        (
            "fenix_oven",
            "light.fenix_cavity_light",
            {},
            {},
            [{"cavityLight": False}],
        ),
        (
            "supex_structured_oven",
            "light.supex_oven_upper_cavity_light",
            {},
            {},
            [{"upperOven": {"cavityLight": False}}],
        ),
    ],
)
async def test_turn_off(
    hass: HomeAssistant,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    appliance_state: dict[str, Any],
    data: dict[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    """Test light turn off command."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    for state_property, state_value in appliance_state.items():
        state.properties["reported"][state_property] = state_value

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]
