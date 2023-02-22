"""Test discovery of entities for device-specific schemas for the Z-Wave JS integration."""
import pytest

from homeassistant.components.zwave_js.discovery import (
    FirmwareVersionRange,
    ZWaveDiscoverySchema,
    ZWaveValueDiscoverySchema,
)
from homeassistant.components.zwave_js.discovery_data_template import (
    DynamicCurrentTempClimateDataTemplate,
)
from homeassistant.core import HomeAssistant


async def test_iblinds_v2(hass: HomeAssistant, client, iblinds_v2, integration) -> None:
    """Test that an iBlinds v2.0 multilevel switch value is discovered as a cover."""
    node = iblinds_v2
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.window_blind_controller")
    assert not state

    state = hass.states.get("cover.window_blind_controller")
    assert state


async def test_ge_12730(hass: HomeAssistant, client, ge_12730, integration) -> None:
    """Test GE 12730 Fan Controller v2.0 multilevel switch is discovered as a fan."""
    node = ge_12730
    assert node.device_class.specific.label == "Multilevel Power Switch"

    state = hass.states.get("light.in_wall_smart_fan_control")
    assert not state

    state = hass.states.get("fan.in_wall_smart_fan_control")
    assert state


async def test_inovelli_lzw36(
    hass: HomeAssistant, client, inovelli_lzw36, integration
) -> None:
    """Test LZW36 Fan Controller multilevel switch endpoint 2 is discovered as a fan."""
    node = inovelli_lzw36
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.family_room_combo")
    assert state.state == "off"

    state = hass.states.get("fan.family_room_combo_2")
    assert state


async def test_vision_security_zl7432(
    hass: HomeAssistant, client, vision_security_zl7432, integration
) -> None:
    """Test Vision Security ZL7432 is caught by the device specific discovery."""
    for entity_id in (
        "switch.in_wall_dual_relay_switch",
        "switch.in_wall_dual_relay_switch_2",
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["assumed_state"]


async def test_lock_popp_electric_strike_lock_control(
    hass: HomeAssistant, client, lock_popp_electric_strike_lock_control, integration
) -> None:
    """Test that the Popp Electric Strike Lock Control gets discovered correctly."""
    assert hass.states.get("lock.node_62") is not None
    assert (
        hass.states.get("binary_sensor.node_62_the_current_status_of_the_door")
        is not None
    )


async def test_fortrez_ssa3_siren(
    hass: HomeAssistant, client, fortrezz_ssa3_siren, integration
) -> None:
    """Test Fortrezz SSA3 siren gets discovered correctly."""
    assert hass.states.get("select.siren_and_strobe_alarm") is not None


async def test_firmware_version_range_exception(hass: HomeAssistant) -> None:
    """Test FirmwareVersionRange exception."""
    with pytest.raises(ValueError):
        ZWaveDiscoverySchema(
            "test",
            ZWaveValueDiscoverySchema(command_class=1),
            firmware_version_range=FirmwareVersionRange(),
        )


async def test_dynamic_climate_data_discovery_template_failure(
    hass: HomeAssistant, multisensor_6
) -> None:
    """Test that initing a DynamicCurrentTempClimateDataTemplate with no data raises."""
    node = multisensor_6
    with pytest.raises(ValueError):
        DynamicCurrentTempClimateDataTemplate().resolve_data(
            node.values[f"{node.node_id}-49-0-Ultraviolet"]
        )
