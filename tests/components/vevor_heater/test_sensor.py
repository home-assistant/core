"""Unit tests for Vevor BLE Heater sensors."""
from typing import Any, Optional
from unittest.mock import patch

from bleak import BLEDevice
from vevor_heater_ble.heater import (
    HeaterError,
    OperationalMode,
    OperationalStatus,
    PowerStatus,
    VevorDevice,
    VevorHeaterStatus,
)

from homeassistant.components.vevor_heater import DOMAIN
from homeassistant.components.vevor_heater.const import DEFAULT_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

FIXTURE_BLE_DEVICE = BLEDevice(
    address="AB:CD:EF:01:23:45", name="FooBar", details=None, rssi=-1
)


async def test_sensors_target_level(
    enable_bluetooth: None, hass: HomeAssistant
) -> None:
    """Tests sensors when the heater is set to fixed level heating."""
    status_to_set = VevorHeaterStatus(power_status=PowerStatus.OFF)

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=FIXTURE_BLE_DEVICE,
    ):

        def update_self_status(self, _):
            self.status = status_to_set

        with patch.object(
            VevorDevice, "refresh_status", autospec=True
        ) as refresh_status:
            refresh_status.side_effect = update_self_status

            entry = MockConfigEntry(
                domain=DOMAIN, unique_id="Foo", data={"address": "AB:CD:EF:01:23:45"}
            )
            entry.add_to_hass(hass)

            assert await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()
            status_to_set = VevorHeaterStatus(
                power_status=PowerStatus.RUNNING,
                operational_mode=OperationalMode.POWER_LEVEL,
                operational_status=OperationalStatus.HEATING,
                elevation=123.45,
                target_power_level=7,
                current_power_level=7,
                input_voltage=12.34,
                combustion_temperature=222,
                room_temperature=25,
                error=HeaterError.NO_ERROR,
            )

            async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_UPDATE_INTERVAL)
            await hass.async_block_till_done()

            for sensor, value, unit in [
                ("operational_mode", "OperationalMode.POWER_LEVEL", None),
                ("operational_status", "OperationalStatus.HEATING", None),
                ("source_voltage", "12.34", "V"),
                ("elevation", "123.45", "m"),
                ("target_temperature", "unknown", "°C"),
                ("target_power_level", "7", None),
                ("current_power_level", "7", None),
                ("combustion_chamber_temperature", "222", "°C"),
                ("room_temperature", "25", "°C"),
                ("error", "HeaterError.NO_ERROR", None),
            ]:
                state = hass.states.get(
                    f"sensor.vevor_{FIXTURE_BLE_DEVICE.name.lower()}_{sensor}"
                )
                _assert_state(state, expected_value=value, expected_unit=unit)

            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

            pass


async def test_sensors_target_temperature(
    enable_bluetooth: None, hass: HomeAssistant
) -> None:
    """Tests sensors when the heater is set to target temperature heating."""
    status_to_set = VevorHeaterStatus(power_status=PowerStatus.OFF)

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=FIXTURE_BLE_DEVICE,
    ):

        def update_self_status(self, _):
            self.status = status_to_set

        with patch.object(
            VevorDevice, "refresh_status", autospec=True
        ) as refresh_status:
            refresh_status.side_effect = update_self_status

            entry = MockConfigEntry(
                domain=DOMAIN, unique_id="Foo", data={"address": "AB:CD:EF:01:23:45"}
            )
            entry.add_to_hass(hass)

            assert await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()
            status_to_set = VevorHeaterStatus(
                power_status=PowerStatus.RUNNING,
                operational_mode=OperationalMode.TARGET_TEMPERATURE,
                operational_status=OperationalStatus.HEATING,
                elevation=123.45,
                target_temperature=30,
                current_power_level=7,
                input_voltage=12.34,
                combustion_temperature=222,
                room_temperature=25,
                error=HeaterError.NO_ERROR,
            )

            async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_UPDATE_INTERVAL)
            await hass.async_block_till_done()

            for sensor, value, unit in [
                ("operational_mode", "OperationalMode.TARGET_TEMPERATURE", None),
                ("operational_status", "OperationalStatus.HEATING", None),
                ("source_voltage", "12.34", "V"),
                ("elevation", "123.45", "m"),
                ("target_temperature", "30", "°C"),
                ("target_power_level", "unknown", None),
                ("current_power_level", "7", None),
                ("combustion_chamber_temperature", "222", "°C"),
                ("room_temperature", "25", "°C"),
                ("error", "HeaterError.NO_ERROR", None),
            ]:
                state = hass.states.get(
                    f"sensor.vevor_{FIXTURE_BLE_DEVICE.name.lower()}_{sensor}"
                )
                _assert_state(state, expected_value=value, expected_unit=unit)
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

            pass


async def test_sensors_off(enable_bluetooth: None, hass: HomeAssistant) -> None:
    """Tests sensors when the heater is off."""
    status_to_set = VevorHeaterStatus(power_status=PowerStatus.OFF)

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=FIXTURE_BLE_DEVICE,
    ):

        def update_self_status(self, _):
            self.status = status_to_set

        with patch.object(
            VevorDevice, "refresh_status", autospec=True
        ) as refresh_status:
            refresh_status.side_effect = update_self_status

            entry = MockConfigEntry(
                domain=DOMAIN, unique_id="Foo", data={"address": "AB:CD:EF:01:23:45"}
            )
            entry.add_to_hass(hass)

            assert await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()
            status_to_set = VevorHeaterStatus(power_status=PowerStatus.OFF)

            async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_UPDATE_INTERVAL)
            await hass.async_block_till_done()

            for sensor, value, unit in [
                ("operational_mode", "unknown", None),
                ("operational_status", "unknown", None),
                ("source_voltage", "unknown", "V"),
                ("elevation", "unknown", "m"),
                ("target_temperature", "unknown", "°C"),
                ("target_power_level", "unknown", None),
                ("current_power_level", "unknown", None),
                ("combustion_chamber_temperature", "unknown", "°C"),
                ("room_temperature", "unknown", "°C"),
                ("error", "unknown", None),
            ]:
                state = hass.states.get(
                    f"sensor.vevor_{FIXTURE_BLE_DEVICE.name.lower()}_{sensor}"
                )
                _assert_state(state, expected_value=value, expected_unit=unit)
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


def _assert_state(
    state: Any, expected_value: Any, expected_unit: Optional[str]
) -> None:
    if expected_value is None:
        # If we expect the state not to be present it can't have any unit.
        # Failing assert indicates a misconfiguration of the test, not a SUT malfunction.
        assert expected_unit is None

        # Now check the SUT
        assert state is None
    else:
        assert state.state == expected_value
        if expected_unit is None:
            assert "unit" not in state.attributes
        else:
            assert state.attributes["unit_of_measurement"] == expected_unit
