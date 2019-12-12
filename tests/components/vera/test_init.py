"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import (
    VeraArmableDevice,
    VeraBinarySensor,
    VeraController,
    VeraCurtain,
    VeraDevice,
    VeraDimmer,
    VeraLock,
    VeraScene,
    VeraSceneController,
    VeraSensor,
    VeraSwitch,
    VeraThermostat,
)

from homeassistant.components.vera import (
    CONF_EXCLUDE,
    CONF_LIGHTS,
    DOMAIN,
    VERA_DEVICES,
    VeraDevice as VeraDeviceEntity,
)
from homeassistant.core import HomeAssistant

from .common import ComponentFactory


def new_vera_device(cls, device_id: int) -> VeraDevice:
    """Create new mocked vera device.."""
    vera_device = MagicMock(spec=cls)  # type: VeraDevice
    vera_device.device_id = device_id
    vera_device.name = f"dev${device_id}"
    return vera_device


def assert_hass_vera_devices(hass: HomeAssistant, platform: str, arr_len: int) -> None:
    """Assert vera devices are present.."""
    assert hass.data[VERA_DEVICES][platform]
    assert len(hass.data[VERA_DEVICES][platform]) == arr_len


async def test_init(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""

    def setup_callback(controller: VeraController, hass_config: dict) -> None:
        hass_config[DOMAIN][CONF_EXCLUDE] = [11]
        hass_config[DOMAIN][CONF_LIGHTS] = [10]

    await vera_component_factory.configure_component(
        hass=hass,
        devices=(
            new_vera_device(VeraDimmer, 1),
            new_vera_device(VeraBinarySensor, 2),
            new_vera_device(VeraSensor, 3),
            new_vera_device(VeraArmableDevice, 4),
            new_vera_device(VeraLock, 5),
            new_vera_device(VeraThermostat, 6),
            new_vera_device(VeraCurtain, 7),
            new_vera_device(VeraSceneController, 8),
            new_vera_device(VeraSwitch, 9),
            new_vera_device(VeraSwitch, 10),
            new_vera_device(VeraSwitch, 11),
        ),
        scenes=(MagicMock(spec=VeraScene),),
        setup_callback=setup_callback,
    )

    assert_hass_vera_devices(hass, "light", 2)
    assert_hass_vera_devices(hass, "binary_sensor", 1)
    assert_hass_vera_devices(hass, "sensor", 2)
    assert_hass_vera_devices(hass, "switch", 2)
    assert_hass_vera_devices(hass, "lock", 1)
    assert_hass_vera_devices(hass, "climate", 1)
    assert_hass_vera_devices(hass, "cover", 1)


def test_vera_device_entity():
    """Test function."""
    controller = MagicMock(spec=VeraController)  # type: VeraController
    controller.serial_number = "SN"
    device = MagicMock(spec=VeraDevice)  # type: VeraDevice
    device.name = "first device"
    device.device_id = "1"
    device.vera_device_id = "1"
    device.battery_level = 23

    entity = VeraDeviceEntity(device, controller)
    assert entity.device_info == {
        "name": device.name,
        "model": "Unknown",
        "manufacturer": "Unknown",
        "connections": {("serial_id", "SN_1")},
        "identifiers": {"SN_1"},
        "battery": 23,
    }
