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

_EMPTY_CIRCULATION_SCHEDULE_DAYS = {
    "monday": [],
    "tuesday": [],
    "wednesday": [],
    "thursday": [],
    "friday": [],
    "saturday": [],
    "sunday": [],
}


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
async def test_current_operation_reflects_circuit_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the water heater's current_operation is the ViCare circuit's active mode."""
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
    assert state.state == "dhw"


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
    ("fixture_file", "ha_mode", "vicare_mode"),
    [
        pytest.param(
            "vicare/Vitodens300W.json",
            "dhw_and_heating",
            "dhwAndHeating",
            id="vitodens300w",
        ),
        pytest.param("vicare/Vitocal250A.json", "heating", "heating", id="vitocal250a"),
        pytest.param(
            "vicare/Vitocal222G_Vitovent300W.json", "dhw", "dhw", id="vitocal222g"
        ),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fixture_file: str,
    ha_mode: str,
    vicare_mode: str,
) -> None:
    """Test set_operation_mode sends the raw ViCare mode reported by the circuit."""
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
    assert ha_mode in entity.operation_list

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
    ("fixture_file", "unsupported_mode"),
    [
        pytest.param(
            "vicare/Vitocal250A.json", "dhw", id="vitocal250a-dhw-not-supported"
        ),
        pytest.param(
            "vicare/Vitocal222G_Vitovent300W.json",
            "heating",
            id="vitocal222g-heating-not-supported",
        ),
    ],
)
async def test_set_operation_mode_not_supported_by_circuit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fixture_file: str,
    unsupported_mode: str,
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
    assert unsupported_mode not in entity.operation_list

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "water_heater",
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                ATTR_OPERATION_MODE: unsupported_mode,
            },
            blocking=True,
        )

    entity._api.service.setProperty.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("fixture_file", "expected_operation_list"),
    [
        pytest.param(
            "vicare/Vitocal250A.json", ["heating", "standby"], id="vitocal250a"
        ),
        pytest.param(
            "vicare/Vitocal222G_Vitovent300W.json",
            ["dhw", "dhw_and_heating", "standby"],
            id="vitocal222g",
        ),
    ],
)
async def test_operation_list_matches_circuit_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fixture_file: str,
    expected_operation_list: list[str],
) -> None:
    """Test operation_list is derived from the raw modes reported by the circuit."""
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
            {
                ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                **_EMPTY_CIRCULATION_SCHEDULE_DAYS,
                "monday": [
                    {
                        "start_time": "06:00",
                        "end_time": "22:00",
                        "mode": "on",
                        "position": 0,
                    }
                ],
            },
            blocking=True,
        )
        mock_set.assert_called_once_with(
            {
                "mon": [
                    {"start": "06:00", "end": "22:00", "mode": "on", "position": 0}
                ],
                "tue": [],
                "wed": [],
                "thu": [],
                "fri": [],
                "sat": [],
                "sun": [],
            }
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_midnight_end(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set_circulation_schedule service accepts a 24:00 end time."""
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
            {
                ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                **_EMPTY_CIRCULATION_SCHEDULE_DAYS,
                "monday": [
                    {
                        "start_time": "16:30",
                        "end_time": "24:00",
                        "mode": "on",
                        "position": 0,
                    }
                ],
            },
            blocking=True,
        )
        mock_set.assert_called_once_with(
            {
                "mon": [
                    {"start": "16:30", "end": "24:00", "mode": "on", "position": 0}
                ],
                "tue": [],
                "wed": [],
                "thu": [],
                "fri": [],
                "sat": [],
                "sun": [],
            }
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_at_device_max_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_circulation_schedule accepts a schedule at the device's maxEntries."""
    monday_slots = [
        {"start_time": "06:00", "end_time": "07:00", "mode": "on", "position": i}
        for i in range(8)
    ]
    expected_monday_slots = [
        {"start": "06:00", "end": "07:00", "mode": "on", "position": i}
        for i in range(8)
    ]
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
    assert entity._circulation_schedule_modes == ["5/25-cycles", "5/10-cycles", "on"]

    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        await hass.services.async_call(
            "vicare",
            SERVICE_SET_CIRCULATION_SCHEDULE,
            {
                ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                **_EMPTY_CIRCULATION_SCHEDULE_DAYS,
                "monday": monday_slots,
            },
            blocking=True,
        )
        mock_set.assert_called_once_with(
            {
                "mon": expected_monday_slots,
                "tue": [],
                "wed": [],
                "thu": [],
                "fri": [],
                "sat": [],
                "sun": [],
            }
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_exceeds_device_max_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_circulation_schedule rejects a schedule exceeding the device's maxEntries."""
    monday_slots = [
        {"start_time": "06:00", "end_time": "07:00", "mode": "on", "position": i}
        for i in range(9)
    ]
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
                {
                    ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                    **_EMPTY_CIRCULATION_SCHEDULE_DAYS,
                    "monday": monday_slots,
                },
                blocking=True,
            )
        mock_set.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_circulation_schedule_service_unsupported_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_circulation_schedule rejects a mode the device does not report."""
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
    assert entity._circulation_schedule_modes == ["5/25-cycles", "5/10-cycles", "on"]

    with patch.object(
        entity._api, "setDomesticHotWaterCirculationSchedule"
    ) as mock_set:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "vicare",
                SERVICE_SET_CIRCULATION_SCHEDULE,
                {
                    ATTR_ENTITY_ID: ENTITY_WATER_HEATER,
                    **_EMPTY_CIRCULATION_SCHEDULE_DAYS,
                    "monday": [
                        {
                            "start_time": "06:00",
                            "end_time": "07:00",
                            "mode": "unsupported-mode",
                            "position": 0,
                        }
                    ],
                },
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
