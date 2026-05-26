"""Test ViCare climate entity."""

from unittest.mock import Mock, patch

import pytest
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import ATTR_HVAC_ACTION, HVACAction
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_component, entity_registry as er

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("phase", "active", "expected_action"),
    [
        ("heating", True, HVACAction.HEATING),
        ("cooling", True, HVACAction.COOLING),
        ("off", False, HVACAction.IDLE),
        ("ready", False, HVACAction.IDLE),
        # Active compressor without a recognisable phase falls back to
        # HEATING (matches the pre-cooling-support behaviour for hybrid
        # devices that may not expose the phase property).
        (None, True, HVACAction.HEATING),
    ],
)
async def test_hvac_action_compressor_phase(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    phase: str | None,
    active: bool,
    expected_action: HVACAction,
) -> None:
    """hvac_action follows compressor.getPhase for heat pumps.

    Regression test for #171849: previously the entity reported HEATING
    whenever any compressor was active, even during cooling mode.
    """
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
    ]
    mock_compressor = Mock()
    mock_compressor.getActive.return_value = active
    if phase is None:
        mock_compressor.getPhase.side_effect = PyViCareNotSupportedFeatureError("phase")
    else:
        mock_compressor.getPhase.return_value = phase

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.vicare.climate.get_compressors",
            return_value=[mock_compressor],
        ),
        patch(
            "homeassistant.components.vicare.climate.get_burners",
            return_value=[],
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        # Force a refresh while the get_compressors/get_burners patches
        # are still active so the entity's update() picks up the mock.
        component: entity_component.EntityComponent = hass.data["climate"]
        for entity in component.entities:
            await entity.async_update_ha_state(force_refresh=True)

    climate_states = [
        state
        for state in hass.states.async_all("climate")
        if state.attributes.get(ATTR_HVAC_ACTION) is not None
    ]
    assert climate_states, "no climate entity exposed hvac_action"
    for state in climate_states:
        assert state.attributes[ATTR_HVAC_ACTION] == expected_action


async def test_hvac_action_multi_compressor_cooling_takes_precedence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Cooling on any compressor must win over heating/unknown on another.

    Regression guard for the order-dependent bug raised on #171945: with
    one compressor reporting `cooling` and a second compressor active
    without a recognisable phase, the result must be COOLING regardless
    of iteration order.
    """
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
    ]
    cooling_compressor = Mock()
    cooling_compressor.getActive.return_value = True
    cooling_compressor.getPhase.return_value = "cooling"
    unknown_compressor = Mock()
    unknown_compressor.getActive.return_value = True
    unknown_compressor.getPhase.side_effect = PyViCareNotSupportedFeatureError("phase")

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.vicare.climate.get_compressors",
            return_value=[unknown_compressor, cooling_compressor],
        ),
        patch(
            "homeassistant.components.vicare.climate.get_burners",
            return_value=[],
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        component: entity_component.EntityComponent = hass.data["climate"]
        for entity in component.entities:
            await entity.async_update_ha_state(force_refresh=True)

    climate_states = [
        state
        for state in hass.states.async_all("climate")
        if state.attributes.get(ATTR_HVAC_ACTION) is not None
    ]
    assert climate_states, "no climate entity exposed hvac_action"
    for state in climate_states:
        assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
