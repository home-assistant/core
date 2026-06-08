"""Test the MELCloud Home climate platform."""

from unittest.mock import AsyncMock

from aiomelcloudhome import (
    ATAFanSpeed,
    ATAOperationMode,
    ATAVaneHorizontal,
    ATAVaneVertical,
    ATWZoneMode,
)
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
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
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, SnapshotAssertion

ATA_ENTITY_ID = "climate.living_room_ac"
ATW_ZONE1_ENTITY_ID = "climate.heat_pump_zone_1"
ATW_ZONE2_ENTITY_ID = "climate.heat_pump_zone_2"


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ATA climate entity state and attributes from fixture data."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ATA_ENTITY_ID)
    assert state == snapshot


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
    mock_control_ata_unit: AsyncMock,
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

    mock_control_ata_unit.assert_called_once_with("ata-unit-uuid-1", **arguments)


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
    mock_control_ata_unit: AsyncMock,
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

    mock_control_ata_unit.assert_called_once_with(
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
    mock_control_ata_unit: AsyncMock,
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

    mock_control_ata_unit.assert_called_once_with(
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
    mock_control_ata_unit: AsyncMock,
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

    mock_control_ata_unit.assert_called_once_with(
        "ata-unit-uuid-1", vane_horizontal_direction=expected_vane
    )


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_ata_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_control_ata_unit: AsyncMock,
) -> None:
    """Test setting target temperature on an ATA unit."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ATA_ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    mock_control_ata_unit.assert_called_once_with(
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
    mock_control_ata_unit: AsyncMock,
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

    mock_control_ata_unit.assert_called_once_with("ata-unit-uuid-1", **expected_kwargs)


@pytest.mark.parametrize(
    ("entity_id", "current_temp", "target_temp"),
    [
        pytest.param(ATW_ZONE1_ENTITY_ID, 20.0, 21.0, id="zone1"),
        pytest.param(ATW_ZONE2_ENTITY_ID, 21.0, 22.0, id="zone2"),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_atw_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    current_temp: float,
    target_temp: float,
) -> None:
    """Test ATW zone climate entity state from fixture data."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == current_temp
    assert state.attributes[ATTR_TEMPERATURE] == target_temp
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
    ]


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
    mock_control_atw_unit: AsyncMock,
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

    mock_control_atw_unit.assert_called_once_with("atw-unit-uuid-1", **expected_kwargs)


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
    mock_control_atw_unit: AsyncMock,
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

    mock_control_atw_unit.assert_called_once_with("atw-unit-uuid-1", **expected_kwargs)


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
    mock_control_atw_unit: AsyncMock,
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

    mock_control_atw_unit.assert_called_once_with("atw-unit-uuid-1", **expected_kwargs)
