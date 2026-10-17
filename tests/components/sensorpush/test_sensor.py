"""Test the SensorPush sensors."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, patch

from sensorpush_ble import (
    DeviceClass,
    DeviceKey,
    SensorDescription,
    SensorDeviceInfo,
    SensorUpdate,
    SensorValue,
    Units,
)

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.sensorpush.const import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import HTPWX_EMPTY_SERVICE_INFO, HTPWX_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    start_monotonic = time.monotonic()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, HTPWX_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.htp_xw_f4d_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "20.11"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "HTP.xw F4D Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.htp_xw_f4d_temperature")
    assert temp_sensor.state == STATE_UNAVAILABLE
    inject_bluetooth_service_info(hass, HTPWX_EMPTY_SERVICE_INFO)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.htp_xw_f4d_temperature")
    assert temp_sensor.state == "20.11"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def _battery_sensor_update() -> SensorUpdate:
    """Return the update a successful battery poll produces."""
    return SensorUpdate(
        title=None,
        devices={
            None: SensorDeviceInfo(
                name="HTP.xw F4D",
                model="HTP.xw",
                manufacturer="SensorPush",
                sw_version=None,
                hw_version=None,
            )
        },
        entity_descriptions={
            DeviceKey(key="battery", device_id=None): SensorDescription(
                device_key=DeviceKey(key="battery", device_id=None),
                device_class=DeviceClass.BATTERY,
                native_unit_of_measurement=Units.PERCENTAGE,
            ),
            DeviceKey(key="voltage", device_id=None): SensorDescription(
                device_key=DeviceKey(key="voltage", device_id=None),
                device_class=DeviceClass.VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
            ),
        },
        entity_values={
            DeviceKey(key="battery", device_id=None): SensorValue(
                device_key=DeviceKey(key="battery", device_id=None),
                name="Battery",
                native_value=75,
            ),
            DeviceKey(key="voltage", device_id=None): SensorValue(
                device_key=DeviceKey(key="voltage", device_id=None),
                name="Voltage",
                native_value=2.85,
            ),
        },
    )


async def test_battery_poll(hass: HomeAssistant, mock_async_poll: AsyncMock) -> None:
    """Test that polling the device creates the battery sensors."""
    mock_async_poll.return_value = _battery_sensor_update()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, HTPWX_SERVICE_INFO)
    await hass.async_block_till_done()

    mock_async_poll.assert_awaited_once()

    battery_sensor = hass.states.get("sensor.htp_xw_f4d_battery")
    assert battery_sensor.state == "75"
    assert battery_sensor.attributes[ATTR_FRIENDLY_NAME] == "HTP.xw F4D Battery"
    assert battery_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor.attributes[ATTR_STATE_CLASS] == "measurement"

    voltage_sensor = hass.states.get("sensor.htp_xw_f4d_voltage")
    assert voltage_sensor.state == "2.85"
    assert voltage_sensor.attributes[ATTR_FRIENDLY_NAME] == "HTP.xw F4D Voltage"
    assert voltage_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_no_poll_without_a_connectable_device(
    hass: HomeAssistant, mock_async_poll: AsyncMock
) -> None:
    """Test we do not poll when nothing in range can connect to the device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensorpush.async_ble_device_from_address",
        return_value=None,
    ):
        inject_bluetooth_service_info(hass, HTPWX_SERVICE_INFO)
        await hass.async_block_till_done()

    mock_async_poll.assert_not_awaited()
    # The advertisement is still parsed, we just never connect.
    assert hass.states.get("sensor.htp_xw_f4d_temperature").state == "20.11"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
