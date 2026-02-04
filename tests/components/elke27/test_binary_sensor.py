"""Tests for Elke27 binary sensor setup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.elke27 import binary_sensor as binary_module
from homeassistant.components.elke27.binary_sensor import async_setup_entry
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.panel_name = None

    @property
    def is_ready(self) -> bool:
        return self._ready

    def subscribe_typed(self, callback: Any) -> Any:
        def _unsub() -> None:
            return None

        return _unsub

    def get_snapshot(self) -> Any:
        return None

    def __getattr__(self, name: str) -> Any:
        if name == "client":
            raise AssertionError("hub.client should not be accessed")
        raise AttributeError(name)


async def test_binary_sensor_uses_zone_definitions(hass: HomeAssistant) -> None:
    """Verify zone definitions drive setup without hub.client usage."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.1"})
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel=SimpleNamespace(
            name="Panel",
            mac="00:11:22:33:44:55",
            serial="123",
            model="X",
            firmware="1",
        ),
        zones={
            1: SimpleNamespace(zone_id=1, name="Zone A", open=False),
            2: SimpleNamespace(zone_id=2, name="Zone B", open=False),
        },
        zone_definitions={
            1: SimpleNamespace(zone_id=1, name="Zone A", definition="UNDEFINED"),
            2: SimpleNamespace(
                zone_id=2, name="Zone B", definition="BURG PERIM INST", zone_type="door"
            ),
        },
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[Any] = []

    def _add_entities(new_entities: list[Any]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)

    assert len(entities) == 1
    assert entities[0]._attr_name == "Zone B"


def test_zone_device_class_mapping() -> None:
    """Verify zone device class mapping."""
    zone = SimpleNamespace(zone_id=1, name="Zone")
    definition = SimpleNamespace(zone_type="motion")
    assert (
        binary_module._zone_device_class(zone, definition)
        == BinarySensorDeviceClass.MOTION
    )
    definition.zone_type = "window"
    assert (
        binary_module._zone_device_class(zone, definition)
        == BinarySensorDeviceClass.WINDOW
    )
    definition.zone_type = "door"
    assert (
        binary_module._zone_device_class(zone, definition)
        == BinarySensorDeviceClass.DOOR
    )
    definition.zone_type = "other"
    assert (
        binary_module._zone_device_class(zone, definition)
        == BinarySensorDeviceClass.OPENING
    )


async def test_binary_sensor_setup_edge_cases(hass: HomeAssistant) -> None:
    """Verify setup handles missing runtime data and snapshots."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.2"})
    entry.add_to_hass(hass)
    entry.runtime_data = None

    entities: list[Any] = []

    def _add_entities(new_entities: list[Any]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        zones=[
            SimpleNamespace(zone_id=1, name="Zone A", open=False),
            SimpleNamespace(zone_id=2, name="Zone B", open=False),
        ],
        zone_definitions={
            1: SimpleNamespace(definition="UNDEFINED"),
            2: SimpleNamespace(definition="BURG PERIM INST", zone_type="door"),
        },
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    snapshot.zones = []
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)

    snapshot.zones.append(SimpleNamespace(zone_id="x", name="Bad", open=False))
    snapshot.zones.append(SimpleNamespace(zone_id=2, name="Dup", open=False))
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)

    coordinator.async_set_updated_data(None)
    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1


def test_zone_icon_and_attributes() -> None:
    """Verify icon selection and attributes."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.3"})
    zone = SimpleNamespace(zone_id=1, name="Zone 1", open=True, bypassed=False)
    zone_def = SimpleNamespace(definition="BURG PERIM INST", zone_type="door")
    sensor = binary_module.Elke27ZoneBinarySensor(
        coordinator, hub, entry, 1, zone, zone_def
    )
    coordinator.data = SimpleNamespace(zones=[zone], zone_definitions={1: zone_def})
    assert sensor.icon == "mdi:window-open"
    assert sensor.extra_state_attributes["definition"] == "BURG PERIM INST"
    zone.open = False
    assert sensor.icon == "mdi:window-closed"
    zone_def.definition = None
    assert sensor.icon is None


def test_zone_definition_helpers() -> None:
    """Verify helper functions with missing data."""
    assert binary_module._zone_definition_entry(None, 1) is None
    assert binary_module._zone_definition_value({}, None) is None
    assert binary_module._zone_name(SimpleNamespace(name=None), None) is None


def test_zone_missing_state() -> None:
    """Verify missing zone returns None state and no icon."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.4"})
    sensor = binary_module.Elke27ZoneBinarySensor(
        coordinator, hub, entry, 1, SimpleNamespace(), None
    )
    assert sensor.is_on is None
    assert sensor.icon is None
    assert sensor.extra_state_attributes == {}
    hub._ready = False
    assert sensor.available is False


def test_zone_is_on_non_bool() -> None:
    """Verify non-bool open values yield None."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.5"})
    zone = SimpleNamespace(zone_id=1, open="yes")
    sensor = binary_module.Elke27ZoneBinarySensor(
        coordinator, hub, entry, 1, zone, None
    )
    coordinator.data = SimpleNamespace(zones=[zone])
    assert sensor.is_on is None
