"""The tests for the mFi switch platform."""
import pytest

import homeassistant.components.mfi.switch as mfi
import homeassistant.components.switch as switch_component
from homeassistant.setup import async_setup_component

import tests.async_mock as mock

PLATFORM = mfi
COMPONENT = switch_component
THING = "switch"
GOOD_CONFIG = {
    "switch": {
        "platform": "mfi",
        "host": "foo",
        "port": 6123,
        "username": "user",
        "password": "pass",
        "ssl": True,
        "verify_ssl": True,
    }
}


async def test_setup_adds_proper_devices(hass):
    """Test if setup adds devices."""
    with mock.patch(
        "homeassistant.components.mfi.switch.MFiClient"
    ) as mock_client, mock.patch(
        "homeassistant.components.mfi.switch.MfiSwitch", side_effect=mfi.MfiSwitch
    ) as mock_switch:
        ports = {
            i: mock.MagicMock(
                model=model, label=f"Port {i}", output=False, data={}, ident=f"abcd-{i}"
            )
            for i, model in enumerate(mfi.SWITCH_MODELS)
        }
        ports["bad"] = mock.MagicMock(model="notaswitch")
        print(ports["bad"].model)
        mock_client.return_value.get_devices.return_value = [
            mock.MagicMock(ports=ports)
        ]
        assert await async_setup_component(hass, COMPONENT.DOMAIN, GOOD_CONFIG)
        await hass.async_block_till_done()
        for ident, port in ports.items():
            if ident != "bad":
                mock_switch.assert_any_call(port)
        assert mock.call(ports["bad"], hass) not in mock_switch.mock_calls


@pytest.fixture(name="port")
def port_fixture():
    """Port fixture."""
    return mock.MagicMock()


@pytest.fixture(name="switch")
def switch_fixture(port):
    """Switch fixture."""
    return mfi.MfiSwitch(port)


async def test_name(port, switch):
    """Test the name."""
    assert port.label == switch.name


async def test_update(port, switch):
    """Test update."""
    switch.update()
    assert port.refresh.call_count == 1
    assert port.refresh.call_args == mock.call()


async def test_update_with_target_state(port, switch):
    """Test update with target state."""
    # pylint: disable=protected-access
    switch._target_state = True
    port.data = {}
    port.data["output"] = "stale"
    switch.update()
    assert port.data["output"] == 1.0
    # pylint: disable=protected-access
    assert switch._target_state is None
    port.data["output"] = "untouched"
    switch.update()
    assert port.data["output"] == "untouched"


async def test_turn_on(port, switch):
    """Test turn_on."""
    switch.turn_on()
    assert port.control.call_count == 1
    assert port.control.call_args == mock.call(True)
    # pylint: disable=protected-access
    assert switch._target_state


async def test_turn_off(port, switch):
    """Test turn_off."""
    switch.turn_off()
    assert port.control.call_count == 1
    assert port.control.call_args == mock.call(False)
    # pylint: disable=protected-access
    assert not switch._target_state


async def test_current_power_w(port, switch):
    """Test current power."""
    port.data = {"active_pwr": 10}
    assert switch.current_power_w == 10


async def test_current_power_w_no_data(port, switch):
    """Test current power if there is no data."""
    port.data = {"notpower": 123}
    assert switch.current_power_w == 0


async def test_device_state_attributes(port, switch):
    """Test the state attributes."""
    port.data = {"v_rms": 1.25, "i_rms": 2.75}
    assert switch.device_state_attributes == {"volts": 1.2, "amps": 2.8}
