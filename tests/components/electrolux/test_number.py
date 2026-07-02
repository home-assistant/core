"""Number tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import load_appliance, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the number entity."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("appliance_fixture", "entity_id", "command_value", "command_payload"),
    [
        (
            "hood",
            "number.ceiling_hood_light_color_temperature",
            10.0,
            {"lightColorTemperature": 10},
        ),
        (
            "hood",
            "number.ceiling_hood_light_color_temperature",
            9.8,
            {"lightColorTemperature": 10},
        ),
        ("hood", "number.ceiling_hood_light_intensity", 10.0, {"lightIntensity": 10}),
        ("hood", "number.ceiling_hood_light_intensity", 9.8, {"lightIntensity": 10}),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    appliance_fixture: str,
    entity_id: str,
    command_value: float,
    command_payload: dict[str, Any],
) -> None:
    """Test states of the number entity."""
    await setup_integration(hass, mock_config_entry)

    appliance_id = load_appliance(appliance_fixture).applianceId

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: command_value},
        blocking=True,
    )
    appliances.send_command.assert_called_once_with(
        appliance_id,
        command_payload,
    )


@pytest.mark.parametrize(
    ("appliance_fixture", "temp_unit", "entity_id", "command_value", "command_payload"),
    [
        (
            "fenix_oven",
            "CELSIUS",
            "number.fenix_target_temperature",
            90.0,
            {"targetTemperatureC": 90.0},
        ),
        (
            "fenix_oven",
            "CELSIUS",
            "number.fenix_target_temperature",
            91.0,
            {"targetTemperatureC": 90.0},
        ),
        (
            "supex_structured_oven",
            "CELSIUS",
            "number.supex_oven_upper_cavity_target_temperature",
            90.0,
            {"upperOven": {"targetTemperatureC": 90.0}},
        ),
        (
            "supex_structured_oven",
            "CELSIUS",
            "number.supex_oven_upper_cavity_target_temperature",
            91.0,
            {"upperOven": {"targetTemperatureC": 90.0}},
        ),
        (
            "supex_structured_oven",
            "FAHRENHEIT",
            "number.supex_oven_upper_cavity_target_temperature",
            91.0,
            {"upperOven": {"targetTemperatureF": 197.0}},
        ),
        (
            "supex_structured_oven",
            "FAHRENHEIT",
            "number.supex_oven_upper_cavity_target_temperature",
            92.0,
            {"upperOven": {"targetTemperatureF": 197.0}},
        ),
        (
            "ayran_fridge",
            "CELSIUS",
            "number.ayran_freezer_target_temperature",
            -20.0,
            {"freezer": {"targetTemperatureC": -20.0}},
        ),
        (
            "ayran_fridge",
            "CELSIUS",
            "number.ayran_freezer_target_temperature",
            -19.1,
            {"freezer": {"targetTemperatureC": -20.0}},
        ),
        (
            "ayran_fridge",
            "CELSIUS",
            "number.ayran_fridge_target_temperature",
            4.0,
            {"fridge": {"targetTemperatureC": 4.0}},
        ),
        (
            "ayran_fridge",
            "CELSIUS",
            "number.ayran_fridge_target_temperature",
            4.4,
            {"fridge": {"targetTemperatureC": 4.0}},
        ),
    ],
)
async def test_set_value_temperature(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    appliance_fixture: str,
    temp_unit: str,
    entity_id: str,
    command_value: float,
    command_payload: dict[str, Any],
) -> None:
    """Test states of the number entity."""

    appliance_id = load_appliance(appliance_fixture).applianceId

    appliance_state = await appliances.get_appliance_state(appliance_id)
    appliance_state.properties["reported"]["temperatureRepresentation"] = temp_unit

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = appliance_state

    await setup_integration(hass, mock_config_entry)

    appliance_id = load_appliance(appliance_fixture).applianceId

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: command_value},
        blocking=True,
    )
    appliances.send_command.assert_called_once_with(
        appliance_id,
        command_payload,
    )
