"""Test updating sensors in the victron_ble integration."""

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest

from homeassistant.components.victron_ble.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .fixtures import (
    VICTRON_BATTERY_MONITOR_SENSORS,
    VICTRON_BATTERY_MONITOR_SERVICE_INFO,
    VICTRON_BATTERY_MONITOR_TOKEN,
    VICTRON_DC_ENERGY_METER_SENSORS,
    VICTRON_DC_ENERGY_METER_SERVICE_INFO,
    VICTRON_DC_ENERGY_METER_TOKEN,
    VICTRON_SOLAR_CHARGER_SENSORS,
    VICTRON_SOLAR_CHARGER_SERVICE_INFO,
    VICTRON_SOLAR_CHARGER_TOKEN,
    VICTRON_VEBUS_SENSORS,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    "sensor_test_info",
    [
        (
            VICTRON_BATTERY_MONITOR_SERVICE_INFO,
            VICTRON_BATTERY_MONITOR_TOKEN,
            VICTRON_BATTERY_MONITOR_SENSORS,
        ),
        (
            VICTRON_DC_ENERGY_METER_SERVICE_INFO,
            VICTRON_DC_ENERGY_METER_TOKEN,
            VICTRON_DC_ENERGY_METER_SENSORS,
        ),
        (
            VICTRON_SOLAR_CHARGER_SERVICE_INFO,
            VICTRON_SOLAR_CHARGER_TOKEN,
            VICTRON_SOLAR_CHARGER_SENSORS,
        ),
        (
            VICTRON_VEBUS_SERVICE_INFO,
            VICTRON_VEBUS_TOKEN,
            VICTRON_VEBUS_SENSORS,
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    sensor_test_info: tuple[BluetoothServiceInfo, str, dict[str, str]],
) -> None:
    """Test updating sensors for a battery monitor."""
    service_info = sensor_test_info[0]
    token = sensor_test_info[1]
    sensors = sensor_test_info[2]

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={CONF_ACCESS_TOKEN: token},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        service_info,
    )

    await hass.async_block_till_done()
    assert (
        len(hass.states.async_all()) == len(sensors) + 1
    )  # device-specific sensors, plus RSSI

    for key, value in sensors.items():
        state = hass.states.get(f"sensor.{key}")
        assert state is not None
        assert state.state == value

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
