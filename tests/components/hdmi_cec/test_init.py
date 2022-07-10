"""Tests for HDMI-CEC component."""
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.hdmi_cec import (
    DOMAIN,
    SERVICE_POWER_ON,
    SERVICE_SELECT_DEVICE,
    SERVICE_SEND_COMMAND,
    SERVICE_STANDBY,
    SERVICE_UPDATE_DEVICES,
    SERVICE_VOLUME,
    CecCommand,
    KeyPressCommand,
    KeyReleaseCommand,
    PhysicalAddress,
    parse_mapping,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component

from tests.common import MockEntity, MockEntityPlatform


@pytest.fixture
def MockTcpAdapter():
    """Mock TcpAdapter."""
    with patch(
        "homeassistant.components.hdmi_cec.TcpAdapter", autospec=True
    ) as MockTcpAdapter:
        yield MockTcpAdapter


@pytest.mark.parametrize(
    "mapping,expected",
    [
        ({}, []),
        (
            {
                "TV": "0.0.0.0",
                "Pi Zero": "1.0.0.0",
                "Fire TV Stick": "2.1.0.0",
                "Chromecast": "2.2.0.0",
                "Another Device": "2.3.0.0",
                "BlueRay player": "3.0.0.0",
            },
            [
                ("TV", "0.0.0.0"),
                ("Pi Zero", "1.0.0.0"),
                ("Fire TV Stick", "2.1.0.0"),
                ("Chromecast", "2.2.0.0"),
                ("Another Device", "2.3.0.0"),
                ("BlueRay player", "3.0.0.0"),
            ],
        ),
        (
            {
                1: "Pi Zero",
                2: {
                    1: "Fire TV Stick",
                    2: "Chromecast",
                    3: "Another Device",
                },
                3: "BlueRay player",
            },
            [
                ("Pi Zero", [1, 0, 0, 0]),
                ("Fire TV Stick", [2, 1, 0, 0]),
                ("Chromecast", [2, 2, 0, 0]),
                ("Another Device", [2, 3, 0, 0]),
                ("BlueRay player", [3, 0, 0, 0]),
            ],
        ),
    ],
)
def test_parse_mapping_physical_address(mapping, expected):
    """Test the device config mapping function."""
    result = parse_mapping(mapping)
    result = [
        (r[0], str(r[1]) if isinstance(r[1], PhysicalAddress) else r[1]) for r in result
    ]
    assert result == expected


# Test Setup


async def test_setup_cec_adapter(hass, MockCecAdapter, MockHDMINetwork):
    """Test the general setup of this component."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    MockCecAdapter.assert_called_once_with(name="HA", activate_source=False)
    MockHDMINetwork.assert_called_once()
    call = MockHDMINetwork.call_args
    assert call.args == (MockCecAdapter.return_value,)
    assert call.kwargs["loop"] in (None, hass.loop)

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_hdmi_network.start.assert_called_once_with()
    mock_hdmi_network.set_new_device_callback.assert_called_once()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_hdmi_network.stop.assert_called_once_with()


@pytest.mark.parametrize("osd_name", ["test", "test_a_long_name"])
async def test_setup_set_osd_name(hass, osd_name, MockCecAdapter):
    """Test the setup of this component with the `osd_name` config setting."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"osd_name": osd_name}})

    MockCecAdapter.assert_called_once_with(name=osd_name[:12], activate_source=False)


async def test_setup_tcp_adapter(hass, MockTcpAdapter, MockHDMINetwork):
    """Test the setup of this component with the TcpAdapter (`host` config setting)."""
    host = "0.0.0.0"

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"host": host}})

    MockTcpAdapter.assert_called_once_with(host, name="HA", activate_source=False)
    MockHDMINetwork.assert_called_once()
    call = MockHDMINetwork.call_args
    assert call.args == (MockTcpAdapter.return_value,)
    assert call.kwargs["loop"] in (None, hass.loop)

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_hdmi_network.start.assert_called_once_with()
    mock_hdmi_network.set_new_device_callback.assert_called_once()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_hdmi_network.stop.assert_called_once_with()


# Test services


async def test_service_power_on(hass, MockHDMINetwork):
    """Test the power on service call."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_POWER_ON,
        {},
        blocking=True,
    )

    mock_hdmi_network.power_on.assert_called_once_with()


async def test_service_standby(hass, MockHDMINetwork):
    """Test the standby service call."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_STANDBY,
        {},
        blocking=True,
    )

    mock_hdmi_network.standby.assert_called_once_with()


async def test_service_select_device_alias(hass, MockHDMINetwork):
    """Test the select device service call with a known alias."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"devices": {"Chromecast": "1.0.0.0"}}}
    )

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_DEVICE,
        {"device": "Chromecast"},
        blocking=True,
    )

    mock_hdmi_network.active_source.assert_called_once()
    physical_address = mock_hdmi_network.active_source.call_args.args[0]
    assert isinstance(physical_address, PhysicalAddress)
    assert str(physical_address) == "1.0.0.0"


class MockCecEntity(MockEntity):
    """Mock CEC entity."""

    @property
    def extra_state_attributes(self):
        """Set the physical address in the attributes."""
        return {"physical_address": self._values["physical_address"]}


async def test_service_select_device_entity(hass, MockHDMINetwork):
    """Test the select device service call with an existing entity."""
    platform = MockEntityPlatform(hass)
    await platform.async_add_entities(
        [MockCecEntity(name="hdmi_3", physical_address="3.0.0.0")]
    )

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_DEVICE,
        {"device": "test_domain.hdmi_3"},
        blocking=True,
    )

    mock_hdmi_network.active_source.assert_called_once()
    physical_address = mock_hdmi_network.active_source.call_args.args[0]
    assert isinstance(physical_address, PhysicalAddress)
    assert str(physical_address) == "3.0.0.0"


async def test_service_select_device_physical_address(hass, MockHDMINetwork):
    """Test the select device service call with a raw physical address."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_DEVICE,
        {"device": "1.1.0.0"},
        blocking=True,
    )

    mock_hdmi_network.active_source.assert_called_once()
    physical_address = mock_hdmi_network.active_source.call_args.args[0]
    assert isinstance(physical_address, PhysicalAddress)
    assert str(physical_address) == "1.1.0.0"


async def test_service_update_devices(hass, MockHDMINetwork):
    """Test the update devices service call."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DEVICES,
        {},
        blocking=True,
    )

    mock_hdmi_network.scan.assert_called_once_with()


@pytest.mark.parametrize(
    "count,calls",
    [
        (3, 3),
        (1, 1),
        (0, 0),
        pytest.param(
            "",
            1,
            marks=pytest.mark.xfail(
                reason="While the code allows for an empty string the schema doesn't allow it",
                raises=vol.MultipleInvalid,
            ),
        ),
    ],
)
@pytest.mark.parametrize("direction,key", [("up", 65), ("down", 66)])
async def test_service_volume_x_times(
    hass, MockHDMINetwork, count, calls, direction, key
):
    """Test the volume service call with steps."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME,
        {direction: count},
        blocking=True,
    )

    assert len(mock_hdmi_network.send_command.call_args_list) == calls * 2
    for i in range(calls):
        press_arg = mock_hdmi_network.send_command.call_args_list[i * 2].args[0]
        release_arg = mock_hdmi_network.send_command.call_args_list[i * 2 + 1].args[0]
        assert isinstance(press_arg, KeyPressCommand)
        assert press_arg.key == key
        assert press_arg.dst == 5
        assert isinstance(release_arg, KeyReleaseCommand)
        assert release_arg.dst == 5


@pytest.mark.parametrize("direction,key", [("up", 65), ("down", 66)])
async def test_service_volume_press(hass, MockHDMINetwork, direction, key):
    """Test the volume service call with press attribute."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME,
        {direction: "press"},
        blocking=True,
    )

    mock_hdmi_network.send_command.assert_called_once()
    arg = mock_hdmi_network.send_command.call_args.args[0]
    assert isinstance(arg, KeyPressCommand)
    assert arg.key == key
    assert arg.dst == 5


@pytest.mark.parametrize("direction,key", [("up", 65), ("down", 66)])
async def test_service_volume_release(hass, MockHDMINetwork, direction, key):
    """Test the volume service call with release attribute."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME,
        {direction: "release"},
        blocking=True,
    )

    mock_hdmi_network.send_command.assert_called_once()
    arg = mock_hdmi_network.send_command.call_args.args[0]
    assert isinstance(arg, KeyReleaseCommand)
    assert arg.dst == 5


@pytest.mark.parametrize(
    "attr,key",
    [
        ("toggle", 67),
        ("on", 101),
        ("off", 102),
        pytest.param(
            "",
            101,
            marks=pytest.mark.xfail(
                reason="The documentation mention it's allowed to pass an empty string, but the schema does not allow this",
                raises=vol.MultipleInvalid,
            ),
        ),
    ],
)
async def test_service_volume_mute(hass, MockHDMINetwork, attr, key):
    """Test the volume service call with mute."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME,
        {"mute": attr},
        blocking=True,
    )

    assert len(mock_hdmi_network.send_command.call_args_list) == 2
    press_arg = mock_hdmi_network.send_command.call_args_list[0].args[0]
    release_arg = mock_hdmi_network.send_command.call_args_list[1].args[0]
    assert isinstance(press_arg, KeyPressCommand)
    assert press_arg.key == key
    assert press_arg.dst == 5
    assert isinstance(release_arg, KeyReleaseCommand)
    assert release_arg.dst == 5


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"raw": "20:0D"}, "20:0d"),
        pytest.param(
            {"cmd": "36"},
            "ff:36",
            marks=pytest.mark.xfail(
                reason="String is converted in hex value, the final result looks like 'ff:24', not what you'd expect."
            ),
        ),
        ({"cmd": 54}, "ff:36"),
        pytest.param(
            {"cmd": "36", "src": "1", "dst": "0"},
            "10:36",
            marks=pytest.mark.xfail(
                reason="String is converted in hex value, the final result looks like 'ff:24', not what you'd expect."
            ),
        ),
        ({"cmd": 54, "src": "1", "dst": "0"}, "10:36"),
        pytest.param(
            {"cmd": "64", "src": "1", "dst": "0", "att": "4f:44"},
            "10:64:4f:44",
            marks=pytest.mark.xfail(
                reason="`att` only accepts a int or a HEX value, it seems good to allow for raw data here.",
                raises=vol.MultipleInvalid,
            ),
        ),
        pytest.param(
            {"cmd": "0A", "src": "1", "dst": "0", "att": "1B"},
            "10:0a:1b",
            marks=pytest.mark.xfail(
                reason="The code tries to run `reduce` on this string and fails.",
                raises=TypeError,
            ),
        ),
        pytest.param(
            {"cmd": "0A", "src": "1", "dst": "0", "att": "01"},
            "10:0a:1b",
            marks=pytest.mark.xfail(
                reason="The code tries to run `reduce` on this as an `int` and fails.",
                raises=TypeError,
            ),
        ),
        pytest.param(
            {"cmd": "0A", "src": "1", "dst": "0", "att": ["1B", "44"]},
            "10:0a:1b:44",
            marks=pytest.mark.xfail(
                reason="While the code shows that it's possible to passthrough a list, the call schema does not allow it.",
                raises=(vol.MultipleInvalid, TypeError),
            ),
        ),
    ],
)
async def test_service_send_command(hass, MockHDMINetwork, data, expected):
    """Test the send command service call."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_hdmi_network = MockHDMINetwork.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        data,
        blocking=True,
    )

    mock_hdmi_network.send_command.assert_called_once()
    command = mock_hdmi_network.send_command.call_args.args[0]
    assert isinstance(command, CecCommand)
    assert str(command) == expected
