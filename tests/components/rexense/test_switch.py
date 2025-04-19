import pytest

import asyncio

from homeassistant.components.rexense.switch import RexenseSwitch

class DummyClient:
    def __init__(self):
        self.device_id = "dev1"
        self.model = "REX-PLUG-01"
        self.switch_state = None
        self.connected = False
        self.called = None

    async def async_set_switch(self, on):
        self.called = on

    signal_update = "signal"
    hass = None

def test_is_on_and_available():
    client = DummyClient()
    switch = RexenseSwitch(client)
    assert switch.is_on is False
    client.switch_state = True
    assert switch.is_on is True
    client.connected = True
    client.switch_state = True
    assert switch.available is True

@pytest.mark.asyncio
async def test_turn_on_off():
    client = DummyClient()
    switch = RexenseSwitch(client)
    await switch.async_turn_on()
    assert client.called is True
    await switch.async_turn_off()
    assert client.called is False
