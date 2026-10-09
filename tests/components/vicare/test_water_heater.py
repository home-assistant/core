"""Test ViCare water heater entity."""

from typing import Any
from unittest.mock import patch

import probatio
import pytest
from PyViCare.PyViCareUtils import PyViCareCommandError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_WATER_HEATER = "water_heater.model0_domestic_hot_water"
CIRCULATION_SCHEDULE_FIXTURES = [Fixture({"type:heatpump"}, "vicare/Vitocal250A.json")]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dhw_active_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test water heater uses direct DHW status for on/off state."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)
        await async_update_entity(hass, ENTITY_WATER_HEATER)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "on"


async def _setup_water_heater(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_vicare: MockPyViCare
) -> None:
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=mock_vicare),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)


async def test_get_circulation_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the DHW circulation schedule."""
    await _setup_water_heater(
        hass, mock_config_entry, MockPyViCare(CIRCULATION_SCHEDULE_FIXTURES)
    )

    response = await hass.services.async_call(
        DOMAIN,
        "get_circulation_schedule",
        {ATTR_ENTITY_ID: ENTITY_WATER_HEATER},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


async def test_set_circulation_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the circulation schedule only replaces the passed days."""
    mock_vicare = MockPyViCare(CIRCULATION_SCHEDULE_FIXTURES)
    await _setup_water_heater(hass, mock_config_entry, mock_vicare)
    device = mock_vicare.devices[0]
    current = device.service.getProperty(
        device.accessor, "heating.dhw.pumps.circulation.schedule"
    )["properties"]["entries"]["value"]

    await hass.services.async_call(
        DOMAIN,
        "set_circulation_schedule",
        {
            ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
            "monday": [
                {"from": "06:00:00", "to": "08:30", "mode": "on"},
                {"from": "22:00", "to": "24:00", "mode": "on"},
            ],
            "sunday": [],
        },
        blocking=True,
    )

    device.service.setProperty.assert_called_once_with(
        device.accessor,
        "heating.dhw.pumps.circulation.schedule",
        "setSchedule",
        {
            "newSchedule": {
                **current,
                "mon": [
                    {"start": "06:00", "end": "08:30", "mode": "on", "position": 0},
                    {"start": "22:00", "end": "24:00", "mode": "on", "position": 1},
                ],
                "sun": [],
            }
        },
    )


async def test_circulation_schedule_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the schedule returned by get can be passed to set unchanged."""
    mock_vicare = MockPyViCare(CIRCULATION_SCHEDULE_FIXTURES)
    await _setup_water_heater(hass, mock_config_entry, mock_vicare)
    device = mock_vicare.devices[0]
    current = device.service.getProperty(
        device.accessor, "heating.dhw.pumps.circulation.schedule"
    )["properties"]["entries"]["value"]

    response = await hass.services.async_call(
        DOMAIN,
        "get_circulation_schedule",
        {ATTR_ENTITY_ID: ENTITY_WATER_HEATER},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "set_circulation_schedule",
        {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, **response[ENTITY_WATER_HEATER]},
        blocking=True,
    )

    device.service.setProperty.assert_called_once_with(
        device.accessor,
        "heating.dhw.pumps.circulation.schedule",
        "setSchedule",
        {"newSchedule": current},
    )


@pytest.mark.parametrize(
    "slot",
    [
        pytest.param({"from": "06:05", "to": "08:00", "mode": "on"}, id="off_grid"),
        pytest.param({"from": "25:00", "to": "08:00", "mode": "on"}, id="bad_hour"),
        pytest.param(
            {"from": "08:00", "to": "06:00", "mode": "on"}, id="to_before_from"
        ),
        pytest.param({"from": "06:00", "to": "06:00", "mode": "on"}, id="empty_range"),
        pytest.param({"from": "06:00", "to": "08:00"}, id="missing_mode"),
    ],
)
async def test_set_circulation_schedule_invalid_slot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    slot: dict[str, str],
) -> None:
    """Test invalid slots are rejected by the service schema."""
    await _setup_water_heater(
        hass, mock_config_entry, MockPyViCare(CIRCULATION_SCHEDULE_FIXTURES)
    )

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_circulation_schedule",
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, "monday": [slot]},
            blocking=True,
        )


async def test_set_circulation_schedule_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a rejected schedule is reported to the user."""
    mock_vicare = MockPyViCare(CIRCULATION_SCHEDULE_FIXTURES)
    await _setup_water_heater(hass, mock_config_entry, mock_vicare)
    mock_vicare.devices[0].service.setProperty.side_effect = PyViCareCommandError(
        "invalid mode"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "set_circulation_schedule",
            {
                ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                "monday": [{"from": "06:00", "to": "08:00", "mode": "foo"}],
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "circulation_schedule_not_set"


@pytest.mark.parametrize(
    ("service", "data", "return_response"),
    [
        pytest.param("get_circulation_schedule", {}, True, id="get"),
        pytest.param(
            "set_circulation_schedule",
            {"monday": [{"from": "06:00", "to": "08:00", "mode": "on"}]},
            False,
            id="set",
        ),
    ],
)
async def test_circulation_schedule_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    return_response: bool,
) -> None:
    """Test devices without a circulation schedule raise a validation error."""
    await _setup_water_heater(
        hass,
        mock_config_entry,
        MockPyViCare([Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]),
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, **data},
            blocking=True,
            return_response=return_response,
        )
    assert exc_info.value.translation_key == "circulation_schedule_not_supported"
