"""Tests for the WLED sensor platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Wifi

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.wled.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.wled.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("init_integration")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2021-11-04 17:36:59+01:00")
async def test_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.wled_rgb_light_uptime",
        "sensor.wled_rgb_light_free_memory",
        "sensor.wled_rgb_light_wi_fi_signal",
        "sensor.wled_rgb_light_wi_fi_rssi",
        "sensor.wled_rgb_light_wi_fi_channel",
        "sensor.wled_rgb_light_wi_fi_bssid",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default WLED sensors."""
    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_wifi_sensors_when_wired(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Wi-Fi sensors are only added once the device uses Wi-Fi."""
    # A wired device reports no signal strength.
    device = mock_wled.update.return_value
    wifi = device.info.wifi
    device.info.wifi = Wifi.from_dict({"bssid": "00:00:00:00:00:00", "rssi": 0})

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for key in ("bssid", "channel", "rssi", "signal"):
        assert hass.states.get(f"sensor.wled_rgb_light_wi_fi_{key}") is None

    # The device is connected over Wi-Fi now.
    device.info.wifi = wifi
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for key in ("bssid", "channel", "rssi", "signal"):
        assert hass.states.get(f"sensor.wled_rgb_light_wi_fi_{key}")

    # Later updates don't add them again.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "does not generate unique IDs" not in caplog.text


async def test_no_current_measurement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test missing current information when the device estimates no current."""
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None


async def test_current_measurement_once_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the current sensors are added once the device reports a current."""
    # WLED reports no current while the light is off.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None

    device.info.leds.max_power = 850
    device.info.leds.power = 470
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get("sensor.wled_rgb_light_max_current"))
    assert state.state == "850"
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "470"

    # Later updates don't add them again.
    updates = mock_wled.update.call_count
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_wled.update.call_count > updates
    assert "does not generate unique IDs" not in caplog.text


async def test_current_measurement_kept_when_not_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test current sensors added before stay while the device reports none."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.wled_rgb_light_estimated_current")

    # The light is off when Home Assistant starts again.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_max_current"))
    assert state.state == "0"
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "0"


async def test_current_measurement_with_per_output_limiters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test estimated current is available when limiting current per output."""
    # Per output limiters leave the global power budget unset, while the
    # device keeps estimating and reporting the current it draws.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 3193

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "3193"


async def test_fail_when_other_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
) -> None:
    """Ensure no data are updated when mac address mismatch."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_ip"))
    assert state.state == "127.0.0.1"

    device = mock_wled.update.return_value
    device.info.mac_address = "invalid"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_ip"))
    assert state.state == "unavailable"


async def _async_setup_with_readings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    readings: dict[str, Any],
) -> dict[str, Any]:
    """Set up a device whose usermods report the given readings."""
    data = await async_load_json_object_fixture(hass, "rgb.json", DOMAIN)
    data["info"]["sensor"] = readings
    mock_wled.update.return_value.update_from_dict(data)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return data


@pytest.mark.parametrize(
    ("readings", "entity_id", "state", "unit", "device_class"),
    [
        # The Temperature usermod, like a DS18B20.
        (
            {"temperature": [21.5, "°C"]},
            "sensor.wled_rgb_light_temperature",
            "21.5",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        ),
        # Home Assistant shows it in the system's unit, Celsius in tests.
        (
            {"temperature": [70.7, "°F"]},
            "sensor.wled_rgb_light_temperature",
            "21.5",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        ),
        # The SHT usermod, which pads its humidity unit with a space.
        (
            {"temp": [22.1, "°C"], "humidity": [48.3, " RH"]},
            "sensor.wled_rgb_light_temperature",
            "22.1",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        ),
        (
            {"temp": [22.1, "°C"], "humidity": [48.3, " RH"]},
            "sensor.wled_rgb_light_humidity",
            "48.3",
            PERCENTAGE,
            SensorDeviceClass.HUMIDITY,
        ),
    ],
)
async def test_usermod_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    readings: dict[str, Any],
    entity_id: str,
    state: str,
    unit: str,
    device_class: SensorDeviceClass,
) -> None:
    """Test the readings usermods report become sensors."""
    await _async_setup_with_readings(hass, mock_config_entry, mock_wled, readings)

    assert (sensor := hass.states.get(entity_id))
    assert sensor.state == state
    assert sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
    assert sensor.attributes[ATTR_DEVICE_CLASS] == device_class


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_usermod_internal_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the chip temperature becomes a diagnostic sensor."""
    await _async_setup_with_readings(
        hass, mock_config_entry, mock_wled, {"Internal Temperature": [47.2, "°C"]}
    )

    assert (sensor := hass.states.get("sensor.wled_rgb_light_internal_temperature"))
    assert sensor.state == "47.2"
    assert (entry := entity_registry.async_get(sensor.entity_id))
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_usermod_internal_temperature_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the chip temperature sensor is disabled by default."""
    await _async_setup_with_readings(
        hass, mock_config_entry, mock_wled, {"Internal Temperature": [47.2, "°C"]}
    )

    assert hass.states.get("sensor.wled_rgb_light_internal_temperature") is None
    assert (
        entry := entity_registry.async_get("sensor.wled_rgb_light_internal_temperature")
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_usermod_readings_without_a_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test readings that aren't a number in a known unit don't become sensors."""
    await _async_setup_with_readings(
        hass,
        mock_config_entry,
        mock_wled,
        {
            # The PIR sensor switch reports motion without a unit.
            "motion": True,
            "temperature": ["warm", "°C"],
            "humidity": [48.3, "grams"],
        },
    )

    assert hass.states.get("sensor.wled_rgb_light_temperature") is None
    assert hass.states.get("sensor.wled_rgb_light_humidity") is None


async def test_usermod_sensor_follows_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a usermod sensor follows its reading, unit, and errors."""
    data = await _async_setup_with_readings(hass, mock_config_entry, mock_wled, {})
    assert hass.states.get("sensor.wled_rgb_light_temperature") is None

    async def async_report(readings: dict[str, Any]) -> None:
        data["info"]["sensor"] = readings
        mock_wled.update.return_value.update_from_dict(data)
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # The usermod starts reporting, like after connecting the sensor.
    await async_report({"temperature": [21.5, "°C"]})
    assert (sensor := hass.states.get("sensor.wled_rgb_light_temperature"))
    assert sensor.state == "21.5"

    # The usermod is set to Fahrenheit; Home Assistant shows it in Celsius.
    await async_report({"temperature": [77, "°F"]})
    assert (sensor := hass.states.get("sensor.wled_rgb_light_temperature"))
    assert sensor.state == "25.0"

    # On a sensor error, the usermod leaves the reading out.
    await async_report({})
    assert (sensor := hass.states.get("sensor.wled_rgb_light_temperature"))
    assert sensor.state == STATE_UNKNOWN
