import pytest
import asyncio

from homeassistant.components.rexense.websocket_client import RexenseWebsocketClient
from homeassistant.core import CoreState


class DummyHass:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.state = CoreState.running

def test_handle_message_updates_last_values_and_switch_state(monkeypatch):
    hass = DummyHass()
    client = RexenseWebsocketClient(hass, 'test', 'REX-PLUG-01', 'url', '1.0.0', [{'EP':1,'Attributes': ['Voltage', 'PowerSwitch'],'Service': ['On', 'Off', 'Toggle']}])
    # Prepare dispatcher_send to capture calls
    events = []
    monkeypatch.setattr(
        'homeassistant.components.rexense.websocket_client.dispatcher_send',
        lambda hass_ins, signal: events.append((hass_ins, signal))
    )
    data = {
        'FunctionCode': 'NotifyStatus',
        'Payload': {
            'Voltage_1': 120,
            'PowerSwitch_1': True
        }
    }
    client._handle_message(data)
    assert client.last_values['Voltage'] == 120
    assert client.switch_state is True
    assert events, 'Expected dispatcher_send to be called'