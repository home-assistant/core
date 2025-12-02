import pytest

from homeassistant.components.rexense.sensor import RexenseSensor
from aiorexense import RexenseWebsocketClient
from homeassistant.components.rexense.const import REXSENSE_SENSOR_TYPES, DOMAIN

class DummyClient:
    def __init__(self):
        self.device_id = 'test'
        self.model = 'REX-PLUG-01'
        self.feature_map = [{'EP':1,'Attributes': ['Voltage']}]
        self.last_values = {'Voltage': 3.3}
        self.signal_update = f"{DOMAIN}_test_update"
        self.connected = True


def test_native_value_and_available(tmp_path, monkeypatch):
    client = DummyClient()
    sensor = RexenseSensor(client, 'Voltage', 'voltage', 'V', None, None)
    assert sensor.native_value == 3.3
    assert sensor.available is True