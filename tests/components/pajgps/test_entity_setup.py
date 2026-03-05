"""
Tests for entity setup of alert switches and binary sensors, and for
device model resolution in get_device_info.

Three-layer alert model:
  Layer 1 — Hardware support:   device.device_models[0][model_field] == 1
  Layer 2 — Currently enabled:  device.<root_field> is not None  (0 = supported but off,
                                                                   1 = supported and on,
                                                                   None = not present on device)
  Layer 3 — Currently triggered: unread notification of matching meldungtyp exists

Covers:
- get_device_info reads model from device.device_models[0]["model"]
- get_device_info falls back to "Unknown" when device_models is empty or None
- async_setup_entry (switch + binary_sensor):
    * creates an entity only when BOTH model support is 1 AND root field is not None
    * creates an entity when root field is 0 (supported but disabled) — not just truthy
    * does NOT create an entity when model field is 0 (hardware unsupported)
    * does NOT create an entity when root field is None (field absent on device)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from homeassistant.components.pajgps.coordinator_data import CoordinatorData
from homeassistant.components.pajgps.const import ALERT_TYPE_TO_DEVICE_FIELD, ALERT_TYPE_TO_MODEL_FIELD

from .test_common import make_coordinator, make_device, ALL_ALERTS_MODEL


# ---------------------------------------------------------------------------
# get_device_info — device model resolution
# ---------------------------------------------------------------------------

class TestGetDeviceInfoModel(unittest.TestCase):
    """Verify that get_device_info reads the model from device.device_models."""

    def _make_coord_with_device(self, device):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[device])
        return coord

    def test_model_read_from_device_models_first_entry(self):
        """Model should come from device_models[0]['model']."""
        device = make_device(1, device_models=[{"model": "PAJ ALLROUND Finder 4G"}])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        self.assertEqual(info["model"], "PAJ ALLROUND Finder 4G")

    def test_model_falls_back_to_unknown_when_device_models_is_empty_list(self):
        """When device_models is an empty list there is no model entry — fall back to 'Unknown'."""
        device = make_device(1, device_models=[])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        self.assertEqual(info["model"], "Unknown")

    def test_model_falls_back_to_unknown_when_device_models_is_none(self):
        """When device_models is None fall back to 'Unknown'."""
        device = make_device(1, device_models=None)
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        self.assertEqual(info["model"], "Unknown")

    def test_model_falls_back_to_unknown_when_model_key_is_none(self):
        """When device_models[0]['model'] is None fall back to 'Unknown'."""
        device = make_device(1, device_models=[{"model": None}])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        self.assertEqual(info["model"], "Unknown")

    def test_model_uses_first_entry_when_multiple_models_present(self):
        """Only the first entry in device_models should be used."""
        device = make_device(
            1,
            device_models=[
                {"model": "First Model"},
                {"model": "Second Model"},
            ],
        )
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        self.assertEqual(info["model"], "First Model")


# ---------------------------------------------------------------------------
# Helpers shared by switch + binary_sensor setup tests
# ---------------------------------------------------------------------------

def _make_hass_and_config_entry(coordinator):
    """Return a fake hass and config_entry wired to the given coordinator."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    config_entry.runtime_data = coordinator

    hass = MagicMock()

    return hass, config_entry


def _make_model_supporting_only(alert_types: set[int]) -> dict:
    """
    Return a device_models entry where only the given alert_types are supported (1),
    all others set to 0.
    """
    return {
        field: (1 if alert_type in alert_types else 0)
        for alert_type, field in ALERT_TYPE_TO_MODEL_FIELD.items()
    }


# ---------------------------------------------------------------------------
# switch.async_setup_entry — entity creation rules
# ---------------------------------------------------------------------------

class TestSwitchSetupEntry(unittest.IsolatedAsyncioTestCase):
    """
    Verify that alert switch entities are created according to the
    three-layer model:
      1. device_models support field must be 1 (hardware supports it)
      2. root device field must not be None (0 = disabled but present, 1 = enabled)
    """

    async def _run_setup(self, device):
        """Run async_setup_entry for the switch platform and return added entities."""
        from homeassistant.components.pajgps import switch as switch_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[device])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added_entities = []

        def fake_add(entities, **kwargs):
            added_entities.extend(entities)

        await switch_module.async_setup_entry(hass, config_entry, fake_add)
        return added_entities

    async def test_entity_created_when_model_supports_and_field_is_one(self):
        """When model support = 1 and root field = 1, entity is created (alert enabled)."""
        root_kwargs = {field: 1 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), len(ALERT_TYPE_TO_DEVICE_FIELD))

    async def test_entity_created_when_model_supports_and_field_is_zero(self):
        """
        When model support = 1 and root field = 0, entity is STILL created.
        0 means supported but currently disabled — entity must exist.
        """
        root_kwargs = {field: 0 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), len(ALERT_TYPE_TO_DEVICE_FIELD))

    async def test_no_entity_when_model_does_not_support_alert(self):
        """
        When model support field = 0, no entity is created regardless of root field value.
        Hardware doesn't support this alert type.
        """
        no_support_model = {field: 0 for field in ALL_ALERTS_MODEL}
        root_kwargs = {field: 1 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[no_support_model], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 0)

    async def test_no_entity_when_root_field_is_none(self):
        """
        When root field is None (field absent on device), no entity is created
        even if the model advertises support.
        """
        root_kwargs = {field: None for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 0)

    async def test_no_entity_when_both_model_unsupported_and_root_none(self):
        """When neither layer passes, no entity is created."""
        no_support_model = {field: 0 for field in ALL_ALERTS_MODEL}
        root_kwargs = {field: None for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[no_support_model], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 0)

    async def test_entities_created_only_for_model_supported_alerts(self):
        """
        When only some alert types are supported by the model,
        only those alert types get entities (root fields all set to 0).
        """
        # Support only the first two alert types
        supported_types = set(list(ALERT_TYPE_TO_DEVICE_FIELD.keys())[:2])
        partial_model = _make_model_supporting_only(supported_types)
        root_kwargs = {field: 0 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[partial_model], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 2)

    async def test_real_world_allround_finder_2g(self):
        """
        Simulate the real JSON example for 'Allround FINDER 2G 2.0' (device_models from fixture).
        Supported: shock, battery, speed, sos.
        Unsupported: drop, power-cut, ignition, voltage.
        """
        # From the JSON fixture:
        allround_model = {
            "alarm_erschuetterung": 1,   # shock     (type 1)
            "alarm_batteriestand": 1,    # battery   (type 2)
            "alarm_sos": 1,              # sos       (type 4)
            "alarm_geschwindigkeit": 1,  # speed     (type 5)
            "alarm_stromunterbrechung": 0,
            "alarm_zuendalarm": 0,
            "alarm_drop": 0,
            "alarm_volt": 0,
        }
        # Root fields from JSON (alarmbewegung=0, alarmsos=1, etc.)
        device = make_device(
            1,
            device_models=[allround_model],
            alarmbewegung=0,
            alarmakkuwarnung=1,
            alarmsos=1,
            alarmgeschwindigkeit=0,
            alarmstromunterbrechung=0,
            alarmzuendalarm=0,
            alarm_fall_enabled=0,
            alarm_volt=0,
        )

        entities = await self._run_setup(device)

        # Only 4 types are hardware-supported: shock(1), battery(2), sos(4), speed(5)
        self.assertEqual(len(entities), 4)

    async def test_no_entities_warning_logged_when_no_devices(self):
        """When there are no devices at all, no entities are added and a warning is logged."""
        from homeassistant.components.pajgps import switch as switch_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added_entities = []

        def fake_add(entities, **kwargs):
            added_entities.extend(entities)  # pragma: no cover

        with patch("homeassistant.components.pajgps.switch._LOGGER") as mock_logger:
            await switch_module.async_setup_entry(hass, config_entry, fake_add)
            mock_logger.warning.assert_called_once()

        self.assertEqual(len(added_entities), 0)


# ---------------------------------------------------------------------------
# binary_sensor.async_setup_entry — entity creation rules
# ---------------------------------------------------------------------------

class TestBinarySensorSetupEntry(unittest.IsolatedAsyncioTestCase):
    """
    Verify that alert binary sensor entities are created according to the
    same three-layer model as switches.
    """

    async def _run_setup(self, device):
        """Run async_setup_entry for the binary_sensor platform and return added entities."""
        from homeassistant.components.pajgps import binary_sensor as bs_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[device])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added_entities = []

        def fake_add(entities, **kwargs):
            added_entities.extend(entities)

        await bs_module.async_setup_entry(hass, config_entry, fake_add)
        return added_entities

    async def test_entity_created_when_model_supports_and_field_is_one(self):
        """When model support = 1 and root field = 1, entity is created."""
        root_kwargs = {field: 1 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), len(ALERT_TYPE_TO_DEVICE_FIELD))

    async def test_entity_created_when_model_supports_and_field_is_zero(self):
        """
        When model support = 1 and root field = 0, entity is STILL created.
        0 means supported but currently disabled — entity must still be present.
        """
        root_kwargs = {field: 0 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), len(ALERT_TYPE_TO_DEVICE_FIELD))

    async def test_no_entity_when_model_does_not_support_alert(self):
        """When model support field = 0, no entity is created regardless of root field value."""
        no_support_model = {field: 0 for field in ALL_ALERTS_MODEL}
        root_kwargs = {field: 1 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[no_support_model], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 0)

    async def test_no_entity_when_root_field_is_none(self):
        """When root field is None, no entity is created even if model supports it."""
        root_kwargs = {field: None for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[dict(ALL_ALERTS_MODEL)], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 0)

    async def test_entities_created_only_for_model_supported_alerts(self):
        """
        When only some alert types are supported by the model,
        only those get entities (root fields all set to 0).
        """
        supported_types = set(list(ALERT_TYPE_TO_DEVICE_FIELD.keys())[:3])
        partial_model = _make_model_supporting_only(supported_types)
        root_kwargs = {field: 0 for field in ALERT_TYPE_TO_DEVICE_FIELD.values()}
        device = make_device(1, device_models=[partial_model], **root_kwargs)

        entities = await self._run_setup(device)

        self.assertEqual(len(entities), 3)

    async def test_real_world_usb_gps_finder_4g(self):
        """
        Simulate the real JSON example for 'USB GPS Finder 4G' (device_models from fixture).
        Supported: sos, speed, voltage.
        Unsupported: shock, battery, drop, power-cut, ignition.
        """
        usb_finder_model = {
            "alarm_erschuetterung": 0,   # shock     (type 1) — NOT supported
            "alarm_batteriestand": 0,    # battery   (type 2) — NOT supported
            "alarm_sos": 1,              # sos       (type 4)
            "alarm_geschwindigkeit": 1,  # speed     (type 5)
            "alarm_stromunterbrechung": 0,
            "alarm_zuendalarm": 0,
            "alarm_drop": 0,
            "alarm_volt": 1,             # voltage   (type 13)
        }
        device = make_device(
            1,
            device_models=[usb_finder_model],
            alarmbewegung=0,
            alarmakkuwarnung=0,
            alarmsos=0,
            alarmgeschwindigkeit=0,
            alarmstromunterbrechung=0,
            alarmzuendalarm=0,
            alarm_fall_enabled=0,
            alarm_volt=0,
        )

        entities = await self._run_setup(device)

        # Only 3 types are hardware-supported: sos(4), speed(5), voltage(13)
        self.assertEqual(len(entities), 3)

    async def test_no_entities_warning_logged_when_no_devices(self):
        """When there are no devices at all, no entities are added and a warning is logged."""
        from homeassistant.components.pajgps import binary_sensor as bs_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added_entities = []

        def fake_add(entities, **kwargs):
            added_entities.extend(entities)  # pragma: no cover

        with patch("homeassistant.components.pajgps.binary_sensor._LOGGER") as mock_logger:
            await bs_module.async_setup_entry(hass, config_entry, fake_add)
            mock_logger.warning.assert_called_once()

        self.assertEqual(len(added_entities), 0)


# ---------------------------------------------------------------------------
# sensor.async_setup_entry — voltage / battery / speed / elevation rules
# ---------------------------------------------------------------------------

class TestSensorSetupEntry(unittest.IsolatedAsyncioTestCase):
    """
    Verify that sensor entities are gated on device_models capability fields:
      - PajGPSVoltageSensor  → only when device_models[0].alarm_volt == 1
      - PajGPSBatterySensor  → only when device_models[0].standalone_battery > 0
                               (or force_battery config option overrides)
      - PajGPSSpeedSensor    → always (every device has speed data)
      - PajGPSElevationSensor → only when fetch_elevation config option is True
    """

    async def _run_setup(self, device, fetch_elevation=False, force_battery=False):
        """Run async_setup_entry for the sensor platform and return added entities."""
        from homeassistant.components.pajgps import sensor as sensor_module

        coord = make_coordinator(fetch_elevation=fetch_elevation, force_battery=force_battery)
        coord.data = CoordinatorData(devices=[device])
        hass, config_entry = _make_hass_and_config_entry(coord)

        # sensor.py reads these from config_entry.data, not from coordinator entry_data
        config_entry.data = {
            "fetch_elevation": fetch_elevation,
            "force_battery": force_battery,
        }

        added_entities = []

        def fake_add(entities, **kwargs):
            added_entities.extend(entities)

        await sensor_module.async_setup_entry(hass, config_entry, fake_add)
        return added_entities

    def _entity_types(self, entities) -> list[str]:
        return [type(e).__name__ for e in entities]

    async def test_voltage_sensor_created_when_model_supports_it(self):
        """alarm_volt == 1 in device_models → voltage sensor entity must be created."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "alarm_volt": 1, "standalone_battery": 1}])

        entities = await self._run_setup(device)

        self.assertIn("PajGPSVoltageSensor", self._entity_types(entities))

    async def test_voltage_sensor_not_created_when_model_does_not_support_it(self):
        """alarm_volt == 0 in device_models → no voltage sensor, even though root field exists."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "alarm_volt": 0, "standalone_battery": 1}])

        entities = await self._run_setup(device)

        self.assertNotIn("PajGPSVoltageSensor", self._entity_types(entities))

    async def test_voltage_sensor_not_created_when_device_models_is_empty(self):
        """No device_models at all → no voltage sensor."""
        device = make_device(1, device_models=[])

        entities = await self._run_setup(device)

        self.assertNotIn("PajGPSVoltageSensor", self._entity_types(entities))

    async def test_battery_sensor_created_when_standalone_battery_is_positive(self):
        """standalone_battery == 1 → battery sensor must be created."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "standalone_battery": 1}])

        entities = await self._run_setup(device)

        self.assertIn("PajGPSBatterySensor", self._entity_types(entities))

    async def test_battery_sensor_not_created_when_standalone_battery_is_zero(self):
        """standalone_battery == 0 (or absent) → no battery sensor."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "standalone_battery": 0}])

        entities = await self._run_setup(device)

        self.assertNotIn("PajGPSBatterySensor", self._entity_types(entities))

    async def test_battery_sensor_not_created_when_standalone_battery_is_negative(self):
        """standalone_battery == -1 (USB-powered device) → no battery sensor."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "standalone_battery": -1}])

        entities = await self._run_setup(device)

        self.assertNotIn("PajGPSBatterySensor", self._entity_types(entities))

    async def test_battery_sensor_created_when_force_battery_overrides(self):
        """force_battery=True creates a battery sensor even when model says no battery."""
        device = make_device(1, device_models=[{**ALL_ALERTS_MODEL, "standalone_battery": -1}])

        entities = await self._run_setup(device, force_battery=True)

        self.assertIn("PajGPSBatterySensor", self._entity_types(entities))

    async def test_speed_sensor_always_created(self):
        """Speed sensor is created for every device regardless of model."""
        device = make_device(1, device_models=[])

        entities = await self._run_setup(device)

        self.assertIn("PajGPSSpeedSensor", self._entity_types(entities))

    async def test_elevation_sensor_created_when_option_enabled(self):
        """Elevation sensor is created only when fetch_elevation is True."""
        device = make_device(1)

        entities = await self._run_setup(device, fetch_elevation=True)

        self.assertIn("PajGPSElevationSensor", self._entity_types(entities))

    async def test_elevation_sensor_not_created_when_option_disabled(self):
        """Elevation sensor is NOT created when fetch_elevation is False."""
        device = make_device(1)

        entities = await self._run_setup(device, fetch_elevation=False)

        self.assertNotIn("PajGPSElevationSensor", self._entity_types(entities))

    async def test_real_world_allround_finder_2g_sensors(self):
        """
        Allround FINDER 2G 2.0: alarm_volt=0, standalone_battery=1.
        Expected: speed + battery, NO voltage.
        """
        allround_model = {
            "model": "Allround FINDER 2G 2.0",
            "alarm_volt": 0,
            "standalone_battery": 1,
        }
        device = make_device(1, device_models=[allround_model])

        entities = await self._run_setup(device)
        types = self._entity_types(entities)

        self.assertIn("PajGPSSpeedSensor", types)
        self.assertIn("PajGPSBatterySensor", types)
        self.assertNotIn("PajGPSVoltageSensor", types)

    async def test_real_world_usb_gps_finder_4g_sensors(self):
        """
        USB GPS Finder 4G: alarm_volt=1, standalone_battery=-1.
        Expected: speed + voltage, NO battery.
        """
        usb_model = {
            "model": "USB GPS Finder 4G",
            "alarm_volt": 1,
            "standalone_battery": -1,
        }
        device = make_device(1, device_models=[usb_model])

        entities = await self._run_setup(device)
        types = self._entity_types(entities)

        self.assertIn("PajGPSSpeedSensor", types)
        self.assertIn("PajGPSVoltageSensor", types)
        self.assertNotIn("PajGPSBatterySensor", types)
