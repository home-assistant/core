"""Test ViCare water heater entity."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vicare.water_heater import (
    ATTR_SCHEDULE,
    SERVICE_SET_DHW_CIRCULATION_SCHEDULE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_WATER_HEATER = "water_heater.model0_domestic_hot_water"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dhw_circulation_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test water heater domestic hot water circulation schedule."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    mock_schedule = {
        "mon": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "tue": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "wed": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "thu": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "fri": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "sat": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
        "sun": [{"mode": "on", "start": "00:00", "end": "24:00", "position": 0}],
    }

    mock_device = MagicMock()
    mock_device.getDomesticHotWaterCirculationSchedule.return_value = mock_schedule

    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
        patch(
            "PyViCare.PyViCareDeviceConfig.PyViCareDeviceConfig.asAutoDetectDevice",
            return_value=mock_device,
        ),
    ):
        state = hass.states.get(ENTITY_WATER_HEATER)
        assert state.state == "on"

        await setup_integration(hass, mock_config_entry)
        await async_update_entity(hass, ENTITY_WATER_HEATER)

        state = hass.states.get(ENTITY_WATER_HEATER)
        assert state.attributes.get(ATTR_SCHEDULE) == mock_schedule

        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_DHW_CIRCULATION_SCHEDULE,
            {ATTR_SCHEDULE: mock_schedule},
            target={"entity_id": ENTITY_WATER_HEATER},
            blocking=True,
        )

        mock_device.setDomesticHotWaterCirculationSchedule.assert_called_once_with(
            mock_schedule
        )


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
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
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
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)
        await async_update_entity(hass, ENTITY_WATER_HEATER)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "on"
