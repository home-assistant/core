"""Test the MELCloud Home climate platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from aiomelcloudhome import (
    ATAFanSpeed,
    ATAOperationMode,
    ATAVaneHorizontal,
    ATAVaneVertical,
    ATWZoneMode,
    UserContext,
)
import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    SnapshotAssertion,
    load_json_value_fixture,
    snapshot_platform,
)

ATA_ENTITY_ID = "climate.living_room_ac"
ATW_ZONE1_ENTITY_ID = "climate.heat_pump_zone_1"
ATW_ZONE2_ENTITY_ID = "climate.heat_pump_zone_2"


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_climate_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all climate entity states and attributes from fixture data."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.CLIMATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("hvac_mode", "arguments"),
    [
        pytest.param(HVACMode.OFF, {"power": False}, id="off"),
        pytest.param(
            HVACMode.HEAT,
            {"power": True, "operation_mode": ATAOperationMode.HEAT},
        ),
        pytest.param(
            HVACMode.COOL,
            {"power": True, "operation_mode": ATAOperationMode.COOL},
        ),
        pytest.param(
            HVACMode.AUTO,
            {"power": True, "operation_mode": ATAOperationMode.AUTOMATIC},
        ),
        pytest.param(
            HVACMode.DRY,
            {"power": True, "operation_mode": ATAOperationMode.DRY},
        ),
        pytest.param(
            HVACMode.FAN_ONLY,
            {"power": True, "operation_mode": ATAOperationMode.FAN},
        ),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    hvac_mode: HVACMode,
    arguments: dict,
) -> None:
    """Test setting HVAC mode on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", **arguments
    )


@pytest.mark.parametrize(
    ("fan_mode", "expected_speed"),
    [
        pytest.param("auto", ATAFanSpeed.AUTO),
        pytest.param("speed_1", ATAFanSpeed.ONE),
        pytest.param("speed_2", ATAFanSpeed.TWO),
        pytest.param("speed_3", ATAFanSpeed.THREE),
        pytest.param("speed_4", ATAFanSpeed.FOUR),
        pytest.param("speed_5", ATAFanSpeed.FIVE),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    fan_mode: str,
    expected_speed: ATAFanSpeed,
) -> None:
    """Test setting fan speed on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", set_fan_speed=expected_speed
    )


@pytest.mark.parametrize(
    ("swing_mode", "expected_vane"),
    [
        pytest.param("auto", ATAVaneVertical.AUTO),
        pytest.param("swing", ATAVaneVertical.SWING),
        pytest.param("position_1", ATAVaneVertical.ONE),
        pytest.param("position_2", ATAVaneVertical.TWO),
        pytest.param("position_3", ATAVaneVertical.THREE),
        pytest.param("position_4", ATAVaneVertical.FOUR),
        pytest.param("position_5", ATAVaneVertical.FIVE),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_swing_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    swing_mode: str,
    expected_vane: ATAVaneVertical,
) -> None:
    """Test setting vertical vane direction on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", vane_vertical_direction=expected_vane
    )


@pytest.mark.parametrize(
    ("swing_mode", "expected_vane"),
    [
        pytest.param("auto", ATAVaneHorizontal.AUTO),
        pytest.param("swing", ATAVaneHorizontal.SWING),
        pytest.param("left", ATAVaneHorizontal.LEFT),
        pytest.param("left_centre", ATAVaneHorizontal.LEFT_CENTRE),
        pytest.param("centre", ATAVaneHorizontal.CENTRE),
        pytest.param("right_centre", ATAVaneHorizontal.RIGHT_CENTRE),
        pytest.param("right", ATAVaneHorizontal.RIGHT),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_swing_horizontal_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    swing_mode: str,
    expected_vane: ATAVaneHorizontal,
) -> None:
    """Test setting horizontal vane direction on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: swing_mode},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", vane_horizontal_direction=expected_vane
    )


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
) -> None:
    """Test setting target temperature on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", set_temperature=22.5
    )


@pytest.mark.parametrize(
    ("service", "expected_kwargs"),
    [
        pytest.param(SERVICE_TURN_ON, {"power": True}),
        pytest.param(SERVICE_TURN_OFF, {"power": False}),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    service: str,
    expected_kwargs: dict,
) -> None:
    """Test turning an ATA unit on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID},
        blocking=True,
    )

    mock_melcloud_client.control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", **expected_kwargs
    )


@pytest.mark.parametrize(
    ("entity_id", "hvac_mode", "expected_kwargs"),
    [
        pytest.param(
            ATW_ZONE1_ENTITY_ID, HVACMode.OFF, {"power": False}, id="zone1_off"
        ),
        pytest.param(
            ATW_ZONE1_ENTITY_ID,
            HVACMode.HEAT,
            {"power": True, "operation_mode_zone1": ATWZoneMode.HEAT_ROOM_TEMPERATURE},
            id="zone1_heat",
        ),
        pytest.param(
            ATW_ZONE2_ENTITY_ID,
            HVACMode.HEAT,
            {"power": True, "operation_mode_zone2": ATWZoneMode.HEAT_ROOM_TEMPERATURE},
            id="zone2_heat",
        ),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_atw_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    entity_id: str,
    hvac_mode: HVACMode,
    expected_kwargs: dict,
) -> None:
    """Test setting HVAC mode on an ATW zone."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_melcloud_client.control_atw_unit.assert_called_once_with(
        "atw-unit-uuid-1", **expected_kwargs
    )


@pytest.mark.parametrize(
    ("entity_id", "expected_kwargs"),
    [
        pytest.param(ATW_ZONE1_ENTITY_ID, {"set_temperature_zone1": 23.0}, id="zone1"),
        pytest.param(ATW_ZONE2_ENTITY_ID, {"set_temperature_zone2": 23.0}, id="zone2"),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_atw_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    entity_id: str,
    expected_kwargs: dict,
) -> None:
    """Test setting target temperature on an ATW zone."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )

    mock_melcloud_client.control_atw_unit.assert_called_once_with(
        "atw-unit-uuid-1", **expected_kwargs
    )


@pytest.mark.parametrize(
    ("service", "expected_kwargs"),
    [
        pytest.param(SERVICE_TURN_ON, {"power": True}),
        pytest.param(SERVICE_TURN_OFF, {"power": False}),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_atw_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    service: str,
    expected_kwargs: dict,
) -> None:
    """Test turning an ATW zone on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ATW_ZONE1_ENTITY_ID},
        blocking=True,
    )

    mock_melcloud_client.control_atw_unit.assert_called_once_with(
        "atw-unit-uuid-1", **expected_kwargs
    )


@pytest.mark.parametrize(
    ("operation_mode", "expected_min", "expected_max"),
    [
        pytest.param("Cool", 16.0, 31.0, id="cool"),
        pytest.param("Automatic", 16.0, 31.0, id="auto"),
        pytest.param("Fan", 7, 35, id="fan_only"),
    ],
)
async def test_ata_temperature_range_by_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    operation_mode: str,
    expected_min: float,
    expected_max: float,
) -> None:
    """Test ATA min/max temperature for cool, auto, and fallback HVAC modes."""
    context = cast(dict[str, Any], load_json_value_fixture("context.json", DOMAIN))
    next(
        setting
        for setting in context["buildings"][0]["airToAirUnits"][0]["settings"]
        if setting["name"] == "OperationMode"
    )["value"] = operation_mode
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ATA_ENTITY_ID)
    assert state is not None
    assert state.attributes["min_temp"] == expected_min
    assert state.attributes["max_temp"] == expected_max


async def test_ata_no_capabilities_temperature_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
) -> None:
    """Test fallback temperature range and hvac_modes when ATA unit has no capabilities."""
    context = cast(dict[str, Any], load_json_value_fixture("context.json", DOMAIN))
    context["buildings"][0]["airToAirUnits"][0]["capabilities"] = None
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ATA_ENTITY_ID)
    assert state is not None
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 35
    assert HVACMode.FAN_ONLY in state.attributes["hvac_modes"]


async def test_atw_zone_temperature_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
) -> None:
    """Test ATW zone min/max temperature read from unit capabilities."""
    context = cast(dict[str, Any], load_json_value_fixture("context.json", DOMAIN))
    context["buildings"][0]["airToWaterUnits"][0]["capabilities"].update(
        {
            "minSetTemperatureZone1": 10.0,
            "maxSetTemperatureZone1": 30.0,
            "minSetTemperatureZone2": 12.0,
            "maxSetTemperatureZone2": 28.0,
        }
    )
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    state1 = hass.states.get(ATW_ZONE1_ENTITY_ID)
    assert state1 is not None
    assert state1.attributes["min_temp"] == 10.0
    assert state1.attributes["max_temp"] == 30.0

    state2 = hass.states.get(ATW_ZONE2_ENTITY_ID)
    assert state2 is not None
    assert state2.attributes["min_temp"] == 12.0
    assert state2.attributes["max_temp"] == 28.0
