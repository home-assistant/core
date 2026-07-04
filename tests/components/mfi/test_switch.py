"""The tests for the mFi switch platform."""

from unittest import mock

import pytest

from homeassistant.components import switch as switch_component
from homeassistant.components.mfi import switch as mfi
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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


async def test_setup_adds_proper_devices(hass: HomeAssistant) -> None:
    """Test if setup adds devices."""
    with (
        mock.patch("homeassistant.components.mfi.switch.MFiClient") as mock_client,
        mock.patch(
            "homeassistant.components.mfi.switch.MfiSwitch", side_effect=mfi.MfiSwitch
        ) as mock_switch,
    ):
        ports = {
            i: mock.MagicMock(
                model=model, label=f"Port {i}", output=False, data={}, ident=f"abcd-{i}"
            )
            for i, model in enumerate(mfi.SWITCH_MODELS)
        }
        ports["bad"] = mock.MagicMock(model="notaswitch")
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


async def test_name(port, switch) -> None:
    """Test the name."""
    assert port.label == switch.name


async def test_update(port, switch) -> None:
    """Test update."""
    switch.update()
    assert port.refresh.call_count == 1
    assert port.refresh.call_args == mock.call()


async def test_update_with_target_state(port, switch) -> None:
    """Test update with target state."""

    switch._target_state = True
    port.data = {}
    port.data["output"] = "stale"
    switch.update()
    assert port.data["output"] == 1.0

    assert switch._target_state is None
    port.data["output"] = "untouched"
    switch.update()
    assert port.data["output"] == "untouched"


async def test_turn_on(port, switch) -> None:
    """Test turn_on."""
    switch.turn_on()
    assert port.control.call_count == 1
    assert port.control.call_args == mock.call(True)

    assert switch._target_state


async def test_turn_off(port, switch) -> None:
    """Test turn_off."""
    switch.turn_off()
    assert port.control.call_count == 1
    assert port.control.call_args == mock.call(False)

    assert not switch._target_state
