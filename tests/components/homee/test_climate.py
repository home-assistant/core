"""Test Homee climate entities."""

from unittest.mock import MagicMock, patch

from pyHomee.const import AttributeType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homee.const import PRESET_MANUAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def setup_mock_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    file: str,
) -> None:
    """Setups a climate node for the tests."""
    mock_homee.nodes = [build_mock_node(file)]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("file", "entity_id", "features", "hvac_modes"),
    [
        (
            "thermostat_only_targettemp.json",
            "climate.test_thermostat_1",
            ClimateEntityFeature.TARGET_TEMPERATURE,
            [HVACMode.HEAT],
        ),
        (
            "thermostat_with_currenttemp.json",
            "climate.test_thermostat_2",
            ClimateEntityFeature.TARGET_TEMPERATURE,
            [HVACMode.HEAT],
        ),
        (
            "thermostat_with_heating_mode.json",
            "climate.test_thermostat_3",
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF,
            [HVACMode.HEAT, HVACMode.OFF],
        ),
        (
            "thermostat_with_preset.json",
            "climate.test_thermostat_4",
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE,
            [HVACMode.HEAT, HVACMode.OFF],
        ),
    ],
)
async def test_climate_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    file: str,
    entity_id: str,
    features: ClimateEntityFeature,
    hvac_modes: list[HVACMode],
) -> None:
    """Test available features of climate entities."""
    await setup_mock_climate(hass, mock_config_entry, mock_homee, file)

    attributes = hass.states.get(entity_id).attributes
    assert attributes["supported_features"] == features
    assert attributes[ATTR_HVAC_MODES] == hvac_modes


async def test_climate_preset_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test available preset modes of climate entities."""
    await setup_mock_climate(
        hass, mock_config_entry, mock_homee, "thermostat_with_preset.json"
    )

    attributes = hass.states.get("climate.test_thermostat_4").attributes
    assert attributes[ATTR_PRESET_MODES] == [
        PRESET_NONE,
        PRESET_ECO,
        PRESET_BOOST,
        PRESET_MANUAL,
    ]


@pytest.mark.parametrize(
    ("attribute_type", "value", "expected"),
    [
        (AttributeType.HEATING_MODE, 0.0, HVACAction.OFF),
        (AttributeType.CURRENT_VALVE_POSITION, 0.0, HVACAction.IDLE),
        (AttributeType.TEMPERATURE, 25.0, HVACAction.IDLE),
        (AttributeType.TEMPERATURE, 18.0, HVACAction.HEATING),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    attribute_type: AttributeType,
    value: float,
    expected: HVACAction,
) -> None:
    """Test hvac action of climate entities."""
    mock_homee.nodes = [build_mock_node("thermostat_with_heating_mode.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    node = mock_homee.nodes[0]
    # set target temperature to 24.0
    node.attributes[0].current_value = 24.0
    attribute = node.get_attribute_by_type(attribute_type)
    attribute.current_value = value
    await setup_integration(hass, mock_config_entry)

    attributes = hass.states.get("climate.test_thermostat_3").attributes
    assert attributes[ATTR_HVAC_ACTION] == expected


@pytest.mark.parametrize(
    ("preset_mode_int", "expected"),
    [
        (0, PRESET_NONE),
        (1, PRESET_NONE),
        (2, PRESET_ECO),
        (3, PRESET_BOOST),
        (4, PRESET_MANUAL),
    ],
)
async def test_current_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    preset_mode_int: int,
    expected: str,
) -> None:
    """Test current preset mode of climate entities."""
    mock_homee.nodes = [build_mock_node("thermostat_with_preset.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    node = mock_homee.nodes[0]
    node.attributes[2].current_value = preset_mode_int
    await setup_integration(hass, mock_config_entry)

    attributes = hass.states.get("climate.test_thermostat_4").attributes
    assert attributes[ATTR_PRESET_MODE] == expected


@pytest.mark.parametrize(
    ("service", "service_data", "expected"),
    [
        (
            SERVICE_TURN_ON,
            {},
            (4, 3, 1),
        ),
        (
            SERVICE_TURN_OFF,
            {},
            (4, 3, 0),
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            (4, 3, 1),
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            (4, 3, 0),
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 20},
            (4, 1, 20),
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_NONE},
            (4, 3, 1),
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_ECO},
            (4, 3, 2),
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_BOOST},
            (4, 3, 3),
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_MANUAL},
            (4, 3, 4),
        ),
    ],
)
async def test_climate_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    service: str,
    service_data: dict,
    expected: tuple[int, int, int],
) -> None:
    """Test available services of climate entities."""
    await setup_mock_climate(
        hass, mock_config_entry, mock_homee, "thermostat_with_preset.json"
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.test_thermostat_4", **service_data},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(*expected)


async def test_climate_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test snapshot of climates."""
    mock_homee.nodes = [
        build_mock_node("thermostat_only_targettemp.json"),
        build_mock_node("thermostat_with_currenttemp.json"),
        build_mock_node("thermostat_with_heating_mode.json"),
        build_mock_node("thermostat_with_preset.json"),
    ]
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
