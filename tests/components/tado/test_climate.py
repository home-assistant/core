"""The climate tests for the tado platform."""

from collections.abc import Generator
from unittest.mock import patch

from PyTado.interface.api.my_tado import TadoZone
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.tado import DOMAIN
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

AIRCON_WITH_SWING = "climate.air_conditioning_with_swing_air_conditioning_with_swing"
AIRCON_WITH_FANLEVEL = (
    "climate.air_conditioning_with_fanlevel_air_conditioning_with_fanlevel"
)


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of climate entities."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_heater_set_temperature(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the set temperature of the heater."""

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_zone_overlay"
        ) as mock_set_state,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: "climate.baseboard_heater_baseboard_heater",
                ClimateServiceArgument.TEMPERATURE: 22.0,
            },
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)


@pytest.mark.parametrize(
    ("hvac_mode", "set_hvac_mode"),
    [
        (HVACMode.HEAT, "HEAT"),
        (HVACMode.DRY, "DRY"),
        (HVACMode.FAN_ONLY, "FAN"),
        (HVACMode.COOL, "COOL"),
        (HVACMode.OFF, "OFF"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_aircon_set_hvac_mode(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hvac_mode: HVACMode,
    set_hvac_mode: str,
) -> None:
    """Test the set hvac mode of the air conditioning."""

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_zone_overlay"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_zone_state",
            return_value=TadoZone(
                zone_id=1,
                current_temp=18.7,
                connection=None,
                current_temp_timestamp="2025-01-02T12:51:52.802Z",
                current_humidity=45.1,
                current_humidity_timestamp="2025-01-02T12:51:52.802Z",
                is_away=False,
                current_hvac_action="IDLE",
                current_fan_speed=None,
                current_fan_level=None,
                current_hvac_mode=set_hvac_mode,
                current_swing_mode="OFF",
                current_vertical_swing_mode="OFF",
                current_horizontal_swing_mode="OFF",
                target_temp=16.0,
                available=True,
                power="ON",
                link="ONLINE",
                ac_power_timestamp=None,
                heating_power_timestamp="2025-01-02T13:01:11.758Z",
                ac_power=None,
                heating_power=None,
                heating_power_percentage=0.0,
                tado_mode="HOME",
                overlay_termination_type="MANUAL",
                overlay_termination_timestamp=None,
                default_overlay_termination_type="MANUAL",
                default_overlay_termination_duration=None,
                preparation=False,
                open_window=False,
                open_window_detected=False,
                open_window_attr={},
                precision=0.1,
            ),
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: "climate.air_conditioning_air_conditioning",
                ClimateServiceArgument.HVAC_MODE: hvac_mode,
            },
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)


@pytest.mark.parametrize(
    ("zone_states_overrides", "entity_id", "hvac_mode", "expected_temperature"),
    [
        pytest.param(
            {"5": "smartac3.off_cold_room.json"},
            AIRCON_WITH_SWING,
            HVACMode.COOL,
            18.0,
            id="cool",
        ),
        pytest.param(
            {"5": "smartac3.off_cold_room.json"},
            AIRCON_WITH_SWING,
            HVACMode.HEAT,
            16.0,
            id="heat",
        ),
        pytest.param(
            {"6": "smartac3.off_cold_room.json"},
            AIRCON_WITH_FANLEVEL,
            HVACMode.DRY,
            16.0,
            id="dry",
        ),
        pytest.param(
            {"5": "smartac3.off_no_temperature.json"},
            AIRCON_WITH_SWING,
            HVACMode.COOL,
            None,
            id="no_room_temperature",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_aircon_turn_on_from_off(
    hass: HomeAssistant,
    entity_id: str,
    hvac_mode: HVACMode,
    expected_temperature: float | None,
) -> None:
    """Test the room temperature is clamped to the mode limits when turning on."""
    assert hass.states.get(entity_id).state == HVACMode.OFF

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.set_zone_overlay"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.HVAC_MODE: hvac_mode,
            },
            blocking=True,
        )

    mock_set_state.assert_called_once()
    assert mock_set_state.call_args.args[2] == expected_temperature
