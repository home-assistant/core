"""Test ViCare water heater entity."""

from unittest.mock import patch

import pytest
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vicare.water_heater import (
    SERVICE_SET_CIRCULATION_SCHEDULE,
    ViCareWater,
)
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DATA_COMPONENT,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_WATER_HEATER = "water_heater.model0_domestic_hot_water"

_FIXTURES: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]


def _get_water_heater_entity(hass: HomeAssistant, entity_id: str) -> ViCareWater:
    """Return the ViCareWater entity object for the given entity_id."""
    component = hass.data[DATA_COMPONENT]
    return next(
        e
        for e in component.entities
        if e.entity_id == entity_id and isinstance(e, ViCareWater)
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
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
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)
        await async_update_entity(hass, ENTITY_WATER_HEATER)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_temperature calls the correct PyViCare API method."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with patch.object(entity._api, "setDomesticHotWaterTemperature") as mock_set:
        await hass.services.async_call(
            "water_heater",
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, ATTR_TEMPERATURE: 55.0},
            blocking=True,
        )
        mock_set.assert_called_once_with(55.0)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes["temperature"] == 55.0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("current_mode", "circuit_modes", "ha_mode", "vicare_mode"),
    [
        pytest.param("standby", ["standby", "dhw"], "on", "dhw", id="on-from-standby"),
        pytest.param("dhw", ["standby", "dhw"], "off", "standby", id="off-from-dhw"),
        pytest.param(
            "dhwAndHeating",
            ["standby", "heating", "dhwAndHeating"],
            "off",
            "heating",
            id="off-preserves-heating",
        ),
        pytest.param(
            "heating",
            ["standby", "heating", "dhwAndHeating"],
            "on",
            "dhwAndHeating",
            id="on-preserves-heating",
        ),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    current_mode: str,
    circuit_modes: list[str],
    ha_mode: str,
    vicare_mode: str,
) -> None:
    """Test set_operation_mode maps HA modes to ViCare circuit modes reported by the device."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with (
        patch.object(entity._circuit, "getActiveMode", return_value=current_mode),
        patch.object(entity._circuit, "getModes", return_value=circuit_modes),
    ):
        await entity.async_update_ha_state(force_refresh=True)

        await hass.services.async_call(
            "water_heater",
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, ATTR_OPERATION_MODE: ha_mode},
            blocking=True,
        )

    entity._api.service.setProperty.assert_called_once_with(
        entity._api.service.accessor,
        "heating.circuits.0.operating.modes.active",
        "setMode",
        {"mode": vicare_mode},
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("fixture_file", "ha_mode"),
    [
        pytest.param(
            "vicare/Vitocal250A.json", "on", id="vitocal250a-dhw-not-supported"
        ),
        pytest.param(
            "vicare/Vitocal222G_Vitovent300W.json",
            "off",
            id="vitocal222g-heating-not-supported",
        ),
    ],
)
async def test_set_operation_mode_not_supported_by_circuit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fixture_file: str,
    ha_mode: str,
) -> None:
    """Test set_operation_mode rejects modes the device's circuit does not support."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare([Fixture(set(), fixture_file)]).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    await entity.async_update_ha_state(force_refresh=True)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "water_heater",
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, ATTR_OPERATION_MODE: ha_mode},
            blocking=True,
        )

    entity._api.service.setProperty.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("fixture_file", "expected_operation_list"),
    [
        pytest.param(
            "vicare/Vitocal250A.json", ["off"], id="vitocal250a-only-off-reachable"
        ),
        pytest.param(
            "vicare/Vitocal222G_Vitovent300W.json",
            ["on"],
            id="vitocal222g-only-on-reachable",
        ),
    ],
)
async def test_operation_list_excludes_unreachable_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fixture_file: str,
    expected_operation_list: list[str],
) -> None:
    """Test operation_list only advertises modes the circuit can actually reach."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare([Fixture(set(), fixture_file)]).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    await entity.async_update_ha_state(force_refresh=True)

    assert entity.operation_list == expected_operation_list

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes["operation_list"] == expected_operation_list


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_temperature_bounds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that min/max temps are updated from the PyViCare API."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with (
        patch.object(
            entity._api,
            "getDomesticHotWaterMinTemperature",
            return_value=15.0,
        ),
        patch.object(
            entity._api,
            "getDomesticHotWaterMaxTemperature",
            return_value=65.0,
        ),
    ):
        await entity.async_update_ha_state(force_refresh=True)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes["min_temp"] == 15.0
    assert state.attributes["max_temp"] == 65.0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_circulation_schedule_in_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that circulation_schedule is exposed as a state attribute."""
    expected_schedule = {
        "active": True,
        "default_mode": "off",
        "mon": [{"start": "06:00", "end": "22:00", "mode": "on", "position": 0}],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with patch.object(
        entity._api,
        "getDomesticHotWaterCirculationSchedule",
        return_value=expected_schedule,
    ):
        await entity.async_update_ha_state(force_refresh=True)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes["circulation_schedule"] == expected_schedule


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set_circulation_schedule service calls the PyViCare API."""
    schedule_payload = {
        "mon": [{"start": "06:00", "end": "22:00", "mode": "on", "position": 0}],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        await hass.services.async_call(
            "vicare",
            SERVICE_SET_CIRCULATION_SCHEDULE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, "schedule": schedule_payload},
            blocking=True,
        )
        mock_set.assert_called_once_with(schedule_payload)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_midnight_end(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set_circulation_schedule service accepts a 24:00 end time."""
    schedule_payload = {
        "mon": [{"start": "16:30", "end": "24:00", "mode": "on", "position": 0}],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        await hass.services.async_call(
            "vicare",
            SERVICE_SET_CIRCULATION_SCHEDULE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, "schedule": schedule_payload},
            blocking=True,
        )
        mock_set.assert_called_once_with(schedule_payload)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_at_device_max_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_circulation_schedule accepts a schedule at the device's maxEntries."""
    schedule_payload = {
        "mon": [
            {"start": "06:00", "end": "07:00", "mode": "on", "position": i}
            for i in range(8)
        ],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(
                [Fixture(set(), "vicare/Vitocal222G_Vitovent300W.json")]
            ).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    await entity.async_update_ha_state(force_refresh=True)
    assert entity._circulation_schedule_max_entries == 8

    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        await hass.services.async_call(
            "vicare",
            SERVICE_SET_CIRCULATION_SCHEDULE,
            {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, "schedule": schedule_payload},
            blocking=True,
        )
        mock_set.assert_called_once_with(schedule_payload)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_exceeds_device_max_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_circulation_schedule rejects a schedule exceeding the device's maxEntries."""
    schedule_payload = {
        "mon": [
            {"start": "06:00", "end": "07:00", "mode": "on", "position": i}
            for i in range(9)
        ],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(
                [Fixture(set(), "vicare/Vitocal222G_Vitovent300W.json")]
            ).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    await entity.async_update_ha_state(force_refresh=True)
    assert entity._circulation_schedule_max_entries == 8

    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "vicare",
                SERVICE_SET_CIRCULATION_SCHEDULE,
                {ATTR_ENTITY_ID: ENTITY_WATER_HEATER, "schedule": schedule_payload},
                blocking=True,
            )
        mock_set.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_circulation_schedule_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that circulation_schedule is absent when not supported by the device."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.WATER_HEATER]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_water_heater_entity(hass, ENTITY_WATER_HEATER)
    with patch.object(
        entity._api,
        "getDomesticHotWaterCirculationSchedule",
        side_effect=PyViCareNotSupportedFeatureError("not supported"),
    ):
        await entity.async_update_ha_state(force_refresh=True)

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert "circulation_schedule" not in state.attributes
