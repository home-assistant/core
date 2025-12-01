"""Test the ThermoPro sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntityDescription
import homeassistant.components.thermopro as thermopro_integration
from homeassistant.components.thermopro import sensor as thermopro_sensor
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TP357_SERVICE_INFO, TP962R_SERVICE_INFO, TP962R_SERVICE_INFO_2

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_tp962r(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_2_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 2 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 6

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_1_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "82.0"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 1 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp357_2142_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "24.1"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp357_2142_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Battery"
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


class CoordinatorStub:
    """Coordinator stub for testing entity restoration behavior."""

    instances: list["CoordinatorStub"] = []

    def __init__(
        self,
        hass: HomeAssistant | None = None,
        logger: MagicMock | None = None,
        *,
        address: str | None = None,
        mode: MagicMock | None = None,
        update_method: MagicMock | None = None,
    ) -> None:
        """Initialize coordinator stub with signature matching real coordinator."""
        # Track created instances to avoid direct hass.data access in tests
        CoordinatorStub.instances.append(self)
        self.calls: list[tuple[MagicMock, type | None]] = []
        self._saw_sensor_entity_description = False
        self._restore_cb: MagicMock | None = None

    def async_register_processor(
        self, processor: MagicMock, entity_description_cls: type | None = None
    ) -> MagicMock:
        """Register a processor and track if SensorEntityDescription was provided."""
        self.calls.append((processor, entity_description_cls))

        if entity_description_cls is SensorEntityDescription:
            self._saw_sensor_entity_description = True

        return lambda: None

    def async_start(self) -> MagicMock:
        """Return a no-op unsub function for start lifecycle."""
        return lambda: None

    def trigger_restore_from_test(self) -> None:
        """Trigger restoration callback if available."""
        if self._saw_sensor_entity_description and self._restore_cb:
            self._restore_cb([])

    def set_restore_callback(self, callback: MagicMock) -> None:
        """Set the callback used to restore entities during the test."""
        self._restore_cb = callback


async def test_thermopro_restores_entities_on_restart_behavior(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that entities are restored on restart via SensorEntityDescription."""

    add_entities_callbacks: list[MagicMock] = []

    orig_add_listener = PassiveBluetoothDataProcessor.async_add_entities_listener

    def wrapped_add_listener(
        self: PassiveBluetoothDataProcessor,
        entity_cls: type,
        add_entities: MagicMock,
    ) -> MagicMock:
        add_entities_callbacks.append(add_entities)
        return orig_add_listener(self, entity_cls, add_entities)

    monkeypatch.setattr(
        PassiveBluetoothDataProcessor,
        "async_add_entities_listener",
        wrapped_add_listener,
    )

    first_called = {"v": False}
    second_called = {"v": False}

    def add_entities_first(entities: list) -> None:
        first_called["v"] = True

    def add_entities_second(entities: list) -> None:
        second_called["v"] = True

    # Patch the integration to avoid platform forwarding and use the coordinator stub
    monkeypatch.setattr(thermopro_integration, "PLATFORMS", [])
    monkeypatch.setattr(
        thermopro_integration, "PassiveBluetoothProcessorCoordinator", CoordinatorStub
    )
    # Ensure a clean slate for stub instance tracking
    CoordinatorStub.instances.clear()

    # First setup using real config entry setup to populate hass.data
    entry1 = MockConfigEntry(domain=DOMAIN, unique_id="00:11:22:33:44:55")
    entry1.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    # Manually set up sensor platform with our callback
    await thermopro_sensor.async_setup_entry(hass, entry1, add_entities_first)
    await hass.async_block_till_done()

    coord = CoordinatorStub.instances[0]
    assert coord.calls, "Processor was not registered on first setup"
    assert not first_called["v"]

    # Second setup (simulating restart)
    entry2 = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF")
    entry2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    await thermopro_sensor.async_setup_entry(hass, entry2, add_entities_second)
    await hass.async_block_till_done()

    assert add_entities_callbacks, "No add_entities callback was registered"
    coord2 = CoordinatorStub.instances[1]
    coord2.set_restore_callback(add_entities_callbacks[-1])

    coord2.trigger_restore_from_test()
    await hass.async_block_till_done()

    assert second_called["v"], (
        "ThermoPro did not trigger restoration on startup. "
        "Ensure async_register_processor(processor, SensorEntityDescription) is used."
    )
