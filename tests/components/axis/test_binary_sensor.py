"""Axis binary sensor platform tests."""

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.setup import async_setup_component

from .test_device import NAME, setup_axis_integration

EVENTS = [
    {
        "operation": "Initialized",
        "topic": "tns1:Device/tnsaxis:Sensor/PIR",
        "source": "sensor",
        "source_idx": "0",
        "type": "state",
        "value": "0",
    },
    {
        "operation": "Initialized",
        "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1",
        "type": "active",
        "value": "1",
    },
]


async def test_platform_manually_configured(hass):
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


async def test_no_binary_sensors(hass):
    """Test that no sensors in Axis results in no sensor entities."""
    await setup_axis_integration(hass)

    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)


async def test_binary_sensors(hass):
    """Test that sensors are loaded properly."""
    device = await setup_axis_integration(hass)

    for event in EVENTS:
        device.api.event.process_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 2

    pir = hass.states.get(f"binary_sensor.{NAME}_pir_0")
    assert pir.state == "off"
    assert pir.name == f"{NAME} PIR 0"

    vmd4 = hass.states.get(f"binary_sensor.{NAME}_vmd4_camera1profile1")
    assert vmd4.state == "on"
    assert vmd4.name == f"{NAME} VMD4 Camera1Profile1"
