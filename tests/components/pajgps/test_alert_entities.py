"""
Tests for binary_sensor.py and switch.py entity property methods.

Covers:
- PajGPSAlertSensor: device_info, is_on (True/False), icon
- PajGPSAlertSwitch: device_info, is_on (True/False/None cases), async_turn_on, async_turn_off
- switch.async_setup_entry warning when no entities
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.pajgps.coordinator_data import CoordinatorData
from homeassistant.components.pajgps.binary_sensor import PajGPSAlertSensor
from homeassistant.components.pajgps.switch import PajGPSAlertSwitch

from .test_common import make_coordinator, make_device, make_notification


def _make_alert_sensor(device_id=1, alert_type=2, notifications=None):
    coord = make_coordinator()
    coord.data = CoordinatorData(
        devices=[make_device(device_id)],
        notifications=notifications or {},
    )
    return PajGPSAlertSensor(coord, device_id, alert_type)


def _make_alert_switch(device_id=1, alert_type=1, alarmbewegung=1):
    coord = make_coordinator()
    coord.data = CoordinatorData(devices=[make_device(device_id, alarmbewegung=alarmbewegung)])
    return PajGPSAlertSwitch(coord, device_id, alert_type)


# ---------------------------------------------------------------------------
# PajGPSAlertSensor
# ---------------------------------------------------------------------------

class TestPajGPSAlertSensor(unittest.TestCase):
    """Tests for PajGPSAlertSensor property methods (binary_sensor.py lines 32, 35-36, 39, 50)."""

    def test_unique_id_is_set(self):
        sensor = _make_alert_sensor(device_id=1, alert_type=2)
        self.assertEqual(sensor._attr_unique_id, "pajgps_test-guid_1_alert_2")

    def test_name_comes_from_alert_names(self):
        sensor = _make_alert_sensor(device_id=1, alert_type=4)
        self.assertEqual(sensor._attr_name, "SOS Alert")

    def test_device_info_returned(self):
        """device_info property must delegate to coordinator (line 32)."""
        sensor = _make_alert_sensor(device_id=1, alert_type=2)
        info = sensor.device_info
        self.assertIsNotNone(info)
        self.assertIn("identifiers", info)

    def test_is_on_true_when_unread_notification_matches(self):
        """is_on returns True when an unread notification of the given type exists (lines 35-36)."""
        notif = make_notification(device_id=1, alert_type=2, is_read=0)
        sensor = _make_alert_sensor(device_id=1, alert_type=2, notifications={1: [notif]})
        self.assertTrue(sensor.is_on)

    def test_is_on_false_when_no_matching_notification(self):
        """is_on returns False when there are no matching unread notifications."""
        notif = make_notification(device_id=1, alert_type=4, is_read=0)  # different type
        sensor = _make_alert_sensor(device_id=1, alert_type=2, notifications={1: [notif]})
        self.assertFalse(sensor.is_on)

    def test_is_on_false_when_no_notifications_at_all(self):
        sensor = _make_alert_sensor(device_id=1, alert_type=2, notifications={})
        self.assertFalse(sensor.is_on)

    def test_icon_bell_alert_when_on(self):
        """icon returns mdi:bell-alert when is_on is True (line 39)."""
        notif = make_notification(device_id=1, alert_type=2, is_read=0)
        sensor = _make_alert_sensor(device_id=1, alert_type=2, notifications={1: [notif]})
        self.assertEqual(sensor.icon, "mdi:bell-alert")

    def test_icon_bell_when_off(self):
        """icon returns mdi:bell when is_on is False."""
        sensor = _make_alert_sensor(device_id=1, alert_type=2, notifications={})
        self.assertEqual(sensor.icon, "mdi:bell")


# ---------------------------------------------------------------------------
# PajGPSAlertSwitch
# ---------------------------------------------------------------------------

class TestPajGPSAlertSwitch(unittest.TestCase):
    """Tests for PajGPSAlertSwitch property methods (switch.py lines 38, 41-49, 51, 53)."""

    def test_unique_id_is_set(self):
        switch = _make_alert_switch(device_id=1, alert_type=1)
        self.assertEqual(switch._attr_unique_id, "pajgps_test-guid_1_switch_1")

    def test_name_comes_from_alert_names(self):
        switch = _make_alert_switch(device_id=1, alert_type=1)
        self.assertEqual(switch._attr_name, "Shock Alert")

    def test_device_info_returned(self):
        """device_info property must delegate to coordinator (line 38)."""
        switch = _make_alert_switch(device_id=1, alert_type=1)
        info = switch.device_info
        self.assertIsNotNone(info)
        self.assertIn("identifiers", info)

    def test_is_on_true_when_field_is_one(self):
        """is_on returns True when the device alert field is 1 (lines 41-49)."""
        switch = _make_alert_switch(device_id=1, alert_type=1, alarmbewegung=1)
        self.assertTrue(switch.is_on)

    def test_is_on_false_when_field_is_zero(self):
        """is_on returns False when the device alert field is 0."""
        switch = _make_alert_switch(device_id=1, alert_type=1, alarmbewegung=0)
        self.assertFalse(switch.is_on)

    def test_is_on_none_when_device_not_found(self):
        """is_on returns None when no device with the given id exists (line 45)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        switch = PajGPSAlertSwitch(coord, device_id=99, alert_type=1)
        self.assertIsNone(switch.is_on)

    def test_is_on_none_when_alert_type_unknown(self):
        """is_on returns None when the alert_type has no mapped field (line 47-48)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        switch = PajGPSAlertSwitch(coord, device_id=1, alert_type=999)
        self.assertIsNone(switch.is_on)


class TestPajGPSAlertSwitchTurnOnOff(unittest.IsolatedAsyncioTestCase):
    """Tests for async_turn_on and async_turn_off (switch.py lines 51, 53)."""

    async def test_turn_on_calls_coordinator(self):
        """async_turn_on must call coordinator.async_update_alert_state with enabled=True (line 51)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.async_update_alert_state = AsyncMock()
        switch = PajGPSAlertSwitch(coord, device_id=1, alert_type=1)

        await switch.async_turn_on()

        coord.async_update_alert_state.assert_awaited_once_with(1, 1, True)

    async def test_turn_off_calls_coordinator(self):
        """async_turn_off must call coordinator.async_update_alert_state with enabled=False (line 53)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.async_update_alert_state = AsyncMock()
        switch = PajGPSAlertSwitch(coord, device_id=1, alert_type=1)

        await switch.async_turn_off()

        coord.async_update_alert_state.assert_awaited_once_with(1, 1, False)


class TestBinarySensorAsyncSetupEntryNoneId(unittest.IsolatedAsyncioTestCase):
    """binary_sensor.async_setup_entry skips devices whose id is None (line 50)."""

    async def test_device_with_none_id_is_skipped(self):
        from unittest.mock import patch
        from homeassistant.components.pajgps import binary_sensor as bs_module

        no_id_device = make_device(1)
        no_id_device.id = None

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[no_id_device])

        config_entry = MagicMock()
        config_entry.runtime_data = coord

        added = []
        with patch("homeassistant.components.pajgps.binary_sensor._LOGGER"):
            await bs_module.async_setup_entry(MagicMock(), config_entry, lambda e, **kw: added.extend(e))

        self.assertEqual(len(added), 0)


class TestSwitchAsyncSetupEntryNoEntities(unittest.IsolatedAsyncioTestCase):
    """async_setup_entry must log a warning when no switch entities are created (line 64)."""

    async def test_warning_logged_when_no_model_support(self):
        from unittest.mock import patch
        from homeassistant.components.pajgps import switch as switch_module

        # Device with no model support for any alert
        no_support_device = make_device(1, device_models=[{field: 0 for field in
            ["alarm_erschuetterung", "alarm_batteriestand", "alarm_sos",
             "alarm_geschwindigkeit", "alarm_stromunterbrechung", "alarm_zuendalarm",
             "alarm_drop", "alarm_volt"]}])

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[no_support_device])

        config_entry = MagicMock()
        config_entry.runtime_data = coord

        added = []
        with patch("homeassistant.components.pajgps.switch._LOGGER") as mock_log:
            await switch_module.async_setup_entry(MagicMock(), config_entry, lambda e, **kw: added.extend(e))
            mock_log.warning.assert_called_once()

        self.assertEqual(len(added), 0)


class TestSwitchAsyncSetupEntryNoneId(unittest.IsolatedAsyncioTestCase):
    """switch.async_setup_entry skips devices whose id is None (line 64)."""

    async def test_device_with_none_id_is_skipped(self):
        from unittest.mock import patch
        from homeassistant.components.pajgps import switch as switch_module

        no_id_device = make_device(1)
        no_id_device.id = None

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[no_id_device])

        config_entry = MagicMock()
        config_entry.runtime_data = coord

        added = []
        with patch("homeassistant.components.pajgps.switch._LOGGER"):
            await switch_module.async_setup_entry(MagicMock(), config_entry, lambda e, **kw: added.extend(e))

        self.assertEqual(len(added), 0)
