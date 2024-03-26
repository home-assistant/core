"""Test the hausbus light class."""
from unittest.mock import patch

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Dimmer import Dimmer
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOff import (
    EvOff as DimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOn import EvOn as DimmerEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.Status import (
    Status as DimmerStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Led import Led
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOn import EvOn as ledEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.Status import Status as ledStatus
from pyhausbus.de.hausbus.homeassistant.proxy.RGBDimmer import RGBDimmer
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOn import (
    EvOn as rgbDimmerEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.Status import (
    Status as rgbDimmerStatus,
)
from pyhausbus.ObjectId import ObjectId
import pytest

from homeassistant.components.hausbus.channel import HausbusChannel
from homeassistant.components.hausbus.device import HausbusDevice
from homeassistant.components.hausbus.light import HausbusLight
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_HS_COLOR, ColorMode
from homeassistant.core import HomeAssistant

from .helpers import create_gateway, create_light_channel


async def test_create_dimmer(hass: HomeAssistant) -> None:
    """Test creating a Dimmer channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Dimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.BRIGHTNESS in light._attr_supported_color_modes


async def test_create_led(hass: HomeAssistant) -> None:
    """Test creating a LED channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Led.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.BRIGHTNESS in light._attr_supported_color_modes


async def test_create_rgbdimmer(hass: HomeAssistant) -> None:
    """Test creating a RGB Dimmer channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = RGBDimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.HS in light._attr_supported_color_modes


async def test_color_mode_generic_light(hass: HomeAssistant) -> None:
    """Test creating a RGB Dimmer channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = ABusFeature(65536)  # = 0x00 01 00 00
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 00 00
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert light.color_mode == ColorMode.ONOFF


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (Dimmer.CLASS_ID, True),
        (Led.CLASS_ID, True),
        (RGBDimmer.CLASS_ID, True),
        (0, False),
    ],
)
async def test_is_light_channel(inputs, expected) -> None:
    """Test return value of is_light_channel."""

    # Assert that the color mode is set according to the light type
    assert HausbusLight.is_light_channel(inputs) == expected


async def test_get_dimmer_status() -> None:
    """Test dimmer get hardware status."""
    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Dimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )
    # Get the dimmer hardware status
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        light.get_hardware_status()
        # Assert that RGBDimmer getStatus was called exactly once
        assert instance.getStatus.call_count == 1


async def test_get_led_status() -> None:
    """Test led get hardware status."""
    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Led.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )
    # Get the led hardware status
    with patch(
        "homeassistant.components.hausbus.light.Led.getStatus", return_value=True
    ):
        light.get_hardware_status()
        # Assert that RGBDimmer getStatus was called exactly once
        assert instance.getStatus.call_count == 1


async def test_get_rgbdimmer_status() -> None:
    """Test rgbdimmer get hardware status."""
    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = RGBDimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )
    # Get the rgbdimmer hardware status
    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.getStatus", return_value=True
    ):
        light.get_hardware_status()
        # Assert that RGBDimmer getStatus was called exactly once
        assert instance.getStatus.call_count == 1


async def test_generic_channel_event_received(hass: HomeAssistant) -> None:
    """Test that an event that was received by a channel that is not a HausBusLight, will not be handled."""
    gateway, _ = await create_gateway(hass)

    # Add a new device to hold the dimmer channel
    device_id = "1"
    module = ModuleId("module", 0, 1, 0, EFirmwareId.ESP32)
    gateway.add_device(device_id, module)

    object_id = ObjectId(65536)  # = 0x00 01 00 00
    channel = HausbusChannel("generic_channel", 0, gateway.get_device(object_id))

    channel_list = gateway.get_channel_list(object_id)
    channel_list[gateway.get_channel_id(object_id)] = channel

    event = {}

    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(object_id.getValue(), receiver, event)

    gateway.busDataReceived(busDataMessage)

    # assert no exception for other channels event


async def test_dimmer_turned_off(hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    dimmer = Dimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, dimmer)

    # event that brightness changed to 50%
    event = DimmerEvOff()

    sender = dimmer.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == "off"
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


async def test_dimmer_turned_on(hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    dimmer = Dimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, dimmer)

    # event that brightness changed to 50%
    event = DimmerEvOn(50, 0)

    sender = dimmer.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == "on"
    # make sure the internal state was updated to 127 (50% of 255)
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        ({"brightness": 50, "duration": 0}, {"state": "on", "brightness": 127}),
        ({"brightness": 0, "duration": 0}, {"state": "off", "brightness": None}),
    ],
)
async def test_dimmer_status_received(inputs, expected, hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    dimmer = Dimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, dimmer)

    event = DimmerStatus(inputs["brightness"], inputs["duration"])

    sender = dimmer.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == expected["state"]
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected["brightness"]


async def test_rgbdimmer_turned_on(hass: HomeAssistant) -> None:
    """Test turning a rgbdimmer on and setting color and brightness."""
    rgbdimmer = RGBDimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, rgbdimmer)

    event = rgbDimmerEvOn(10, 20, 30, 0)

    sender = rgbdimmer.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == "on"
    assert state.attributes.get(ATTR_BRIGHTNESS) == 76
    assert state.attributes.get(ATTR_HS_COLOR) == (210, 67)


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (
            {
                "brightnessRed": 10,
                "brightnessGreen": 20,
                "brightnessBlue": 30,
                "duration": 0,
            },
            {"state": "on", "brightness": 76, "hs": (210, 67)},
        ),
        (
            {
                "brightnessRed": 0,
                "brightnessGreen": 0,
                "brightnessBlue": 0,
                "duration": 0,
            },
            {"state": "off", "brightness": None, "hs": None},
        ),
    ],
)
async def test_rgbdimmer_status_received(inputs, expected, hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    rgbdimmer = RGBDimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, rgbdimmer)

    event = rgbDimmerStatus(
        inputs["brightnessRed"],
        inputs["brightnessGreen"],
        inputs["brightnessBlue"],
        inputs["duration"],
    )

    sender = rgbdimmer.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == expected["state"]
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected["brightness"]
    assert state.attributes.get(ATTR_HS_COLOR) == expected["hs"]


async def test_led_turned_on(hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    led = Led.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Led.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, led)

    # event that brightness changed to 50%
    event = ledEvOn(50, 0)

    sender = led.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == "on"
    # make sure the internal state was updated to 127 (50% of 255)
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        ({"brightness": 50, "duration": 0}, {"state": "on", "brightness": 127}),
        ({"brightness": 0, "duration": 0}, {"state": "off", "brightness": None}),
    ],
)
async def test_led_status_received(inputs, expected, hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    led = Led.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Led.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, led)

    event = ledStatus(inputs["brightness"], inputs["duration"])

    sender = led.getObjectId()  # own object id
    receiver = 0x270E0000  # own object id
    busDataMessage = BusDataMessage(sender, receiver, event)

    gateway.busDataReceived(busDataMessage)

    await hass.async_block_till_done()

    state = hass.states.get(channel.entity_id)

    assert state.state == expected["state"]
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected["brightness"]


async def test_turn_on_dimmer(hass: HomeAssistant) -> None:
    """Test turning a dimmer on and set brightness."""
    dimmer = Dimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, dimmer)

    kwargs = {ATTR_BRIGHTNESS: 128}

    with patch(
        "homeassistant.components.hausbus.light.Dimmer.setBrightness", return_value=True
    ) as mock_set_brightness:
        await channel.async_turn_on(**kwargs)
        mock_set_brightness.assert_called_with(50, 0)


async def test_turn_on_led(hass: HomeAssistant) -> None:
    """Test turning a led on and set brightness."""
    led = Led.create(1, 1)

    # Add the led channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Led.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, led)

    kwargs = {ATTR_BRIGHTNESS: 128}

    with patch(
        "homeassistant.components.hausbus.light.Led.on", return_value=True
    ) as mock_turn_on:
        await channel.async_turn_on(**kwargs)
        mock_turn_on.assert_called_with(50, 0, 0)


async def test_turn_on_rgbdimmer(hass: HomeAssistant) -> None:
    """Test turning a rgb dimmer on and set color."""
    rgbdimmer = RGBDimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, rgbdimmer)

    kwargs = {ATTR_BRIGHTNESS: 76, ATTR_HS_COLOR: (210, 67)}

    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.setColor", return_value=True
    ) as mock_set_color:
        await channel.async_turn_on(**kwargs)
        mock_set_color.assert_called_with(10, 20, 30, 0)


async def test_turn_off_dimmer(hass: HomeAssistant) -> None:
    """Test turning a dimmer off."""
    dimmer = Dimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Dimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, dimmer)

    kwargs = {}

    with patch(
        "homeassistant.components.hausbus.light.Dimmer.setBrightness", return_value=True
    ) as mock_set_brightness:
        await channel.async_turn_off(**kwargs)
        mock_set_brightness.assert_called_with(0, 0)


async def test_turn_off_led(hass: HomeAssistant) -> None:
    """Test turning a led off."""
    led = Led.create(1, 1)

    # Add the led channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.Led.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, led)

    kwargs = {}

    with patch(
        "homeassistant.components.hausbus.light.Led.off", return_value=True
    ) as mock_turn_off:
        await channel.async_turn_off(**kwargs)
        mock_turn_off.assert_called_with(0)


async def test_turn_off_rgbdimmer(hass: HomeAssistant) -> None:
    """Test turning a rgb dimmer off."""
    rgbdimmer = RGBDimmer.create(1, 1)

    # Add the dimmer channel to the gateways channel list
    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.getStatus", return_value=True
    ):
        gateway, channel = await create_light_channel(hass, rgbdimmer)

    kwargs = {}

    with patch(
        "homeassistant.components.hausbus.light.RGBDimmer.setColor", return_value=True
    ) as mock_set_color:
        await channel.async_turn_off(**kwargs)
        mock_set_color.assert_called_with(0, 0, 0, 0)
