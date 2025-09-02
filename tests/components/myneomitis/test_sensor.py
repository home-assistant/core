"""Tests for MyNeoMitis sensor integration."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.components.myneomitis.sensor import (
    DevicesEnergySensor,
    NTCTemperatureSensor,
    async_setup_entry,
)
from homeassistant.components.myneomitis.utils import CtnType
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_radiator_energy_sensor_native_value_and_update() -> None:
    """Test the native value and update functionality of DevicesEnergySensor."""
    device = {
        "_id": "dev1",
        "name": "Salon",
        "state": {
            "consumption": 12345  # in Wh
        },
        "connected": True,
    }

    mock_api = AsyncMock()
    mock_api.get_device_state.return_value = {"state": {"consumption": 23456}}

    sensor = DevicesEnergySensor(mock_api, device, device["state"]["consumption"])

    assert sensor.name == "MyNeo Salon Energy"
    assert sensor.native_value == 0.0

    sensor.hass = MagicMock()
    sensor.entity_id = "sensor.myneo_salon_energy"

    await sensor.async_added_to_hass()

    with patch.object(sensor, "async_write_ha_state"):
        await sensor.async_update()

    assert sensor.native_value == 0.0


async def test_ntc_temperature_sensor_valid_temp_and_update() -> None:
    """Test the valid temperature and update functionality of NTCTemperatureSensor."""
    device = {
        "_id": "dev2",
        "name": "Chamber",
        "rfid": "ABC123",
        "parents": "gateway=gateway123",
        "state": {"ntc1Temp": 21.5},
        "connected": True,
    }

    mock_api = AsyncMock()
    mock_api.get_sub_device_state.return_value = [
        {"rfid": "ABC123", "state": {"ntc1Temp": 23.0}}
    ]

    sensor = NTCTemperatureSensor(mock_api, device, 1, CtnType.FLOOR)

    assert "Chamber" in sensor.name
    assert sensor.native_value == 21.5

    sensor.hass = MagicMock()
    sensor.entity_id = "sensor.myneo_chamber_floor_temp_1"

    await sensor.async_added_to_hass()

    with patch.object(sensor, "async_write_ha_state"):
        await sensor.async_update()

    assert sensor.native_value == 23.0


async def test_ntc_temperature_sensor_invalid_temp() -> None:
    """Test the behavior of NTCTemperatureSensor with an invalid temperature."""
    device = {
        "_id": "dev3",
        "name": "Bureau",
        "rfid": "RFID42",
        "parents": "gateway=g1",
        "state": {
            "ntc0Temp": -50  # invalid
        },
        "connected": True,
    }

    sensor = NTCTemperatureSensor(AsyncMock(), device, 0, CtnType.OUTSIDE)
    assert sensor.native_value is None


async def test_dynamic_sensor_added_on_link_event(hass: HomeAssistant) -> None:
    """Test dynamic addition of energy sensor on WebSocket link."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyNeomitis",
        data={"email": "x", "password": "y"},
    )
    entry.add_to_hass(hass)

    callbacks = {}

    def register_discovery_callback(cb):
        callbacks["discovery"] = cb

    def register_removal_callback(cb):
        callbacks["removal"] = cb

    fake_api = Mock()
    fake_api.sio.connected = True
    fake_api.register_listener = lambda *_: None
    fake_api.register_discovery_callback = register_discovery_callback
    fake_api.register_removal_callback = register_removal_callback

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": fake_api,
        "devices": [],
    }

    added = []

    def fake_add(entities):
        added.extend(entities)

    await async_setup_entry(hass, entry, fake_add)

    linked_device = {
        "_id": "sensor123",
        "name": "Radiateur",
        "model": "EV30",
        "state": {"consumption": 123456},
    }

    callbacks["discovery"](linked_device)
    assert len(added) == 1
    entity = added[0]
    assert isinstance(entity, DevicesEnergySensor)
    assert "Energy" in entity.name
    assert entity.unique_id == "myneo_sensor123_energy"


async def test_dynamic_sensor_removed_on_unlink_event(hass: HomeAssistant) -> None:
    """Test dynamic removal of energy sensor on WebSocket unlink event."""

    class DummySensor(DevicesEnergySensor):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.async_remove_called = False

        async def async_remove(self) -> None:
            self.async_remove_called = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyNeomitis",
        data={"email": "x", "password": "y"},
    )
    entry.add_to_hass(hass)

    callbacks = {}

    def register_discovery_callback(cb):
        callbacks["discovery"] = cb

    def register_removal_callback(cb):
        callbacks["removal"] = cb

    fake_api = Mock()
    fake_api.sio.connected = True
    fake_api.register_listener = lambda *_: None
    fake_api.register_discovery_callback = register_discovery_callback
    fake_api.register_removal_callback = register_removal_callback

    device = {
        "_id": "sensorX",
        "name": "Radiateur",
        "model": "EV30",
        "state": {"consumption": 88888},
    }

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": fake_api,
        "devices": [device],
    }

    added = []

    def fake_add(entities):
        added.extend(entities)

    with patch(
        "homeassistant.components.myneomitis.sensor.DevicesEnergySensor", DummySensor
    ):
        await async_setup_entry(hass, entry, fake_add)

    assert len(added) == 1
    entity = added[0]
    assert not entity.async_remove_called

    callbacks["removal"]("sensorX")
    await hass.async_block_till_done()

    assert entity.async_remove_called
