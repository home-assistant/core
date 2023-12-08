"""Axis binary sensor platform tests."""
from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import NAME


async def test_platform_manually_configured(hass: HomeAssistant) -> None:
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass,
            BINARY_SENSOR_DOMAIN,
            {BINARY_SENSOR_DOMAIN: {"platform": AXIS_DOMAIN}},
        )
        is True
    )

    assert AXIS_DOMAIN not in hass.data


async def test_no_binary_sensors(hass: HomeAssistant, setup_config_entry) -> None:
    """Test that no sensors in Axis results in no sensor entities."""
    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)


async def test_binary_sensors(
    hass: HomeAssistant, setup_config_entry, mock_rtsp_event
) -> None:
    """Test that sensors are loaded properly."""
    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:Sensor/PIR",
        data_type="state",
        data_value="0",
        source_name="sensor",
        source_idx="0",
    )
    mock_rtsp_event(
        topic="tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1",
        data_type="active",
        data_value="1",
    )
    # Unsupported event
    mock_rtsp_event(
        topic="tns1:PTZController/tnsaxis:PTZPresets/Channel_1",
        data_type="on_preset",
        data_value="1",
        source_name="PresetToken",
        source_idx="0",
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 2

    pir = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0")
    assert pir.state == STATE_OFF
    assert pir.name == f"{NAME} PIR 0"
    assert pir.attributes["device_class"] == BinarySensorDeviceClass.MOTION

    vmd4 = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_vmd4_profile_1")
    assert vmd4.state == STATE_ON
    assert vmd4.name == f"{NAME} VMD4 Profile 1"
    assert vmd4.attributes["device_class"] == BinarySensorDeviceClass.MOTION
