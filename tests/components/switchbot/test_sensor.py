"""Test the switchbot sensors."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    CIRCULATOR_FAN_SERVICE_INFO,
    EVAPORATIVE_HUMIDIFIER_SERVICE_INFO,
    HUB3_SERVICE_INFO,
    HUBMINI_MATTER_SERVICE_INFO,
    LEAK_SERVICE_INFO,
    RELAY_SWITCH_2PM_SERVICE_INFO,
    REMOTE_SERVICE_INFO,
    WOHAND_SERVICE_INFO,
    WOHUB2_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO,
    WORELAY_SWITCH_1PM_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 2

    battery_sensor = hass.states.get("sensor.test_name_battery")
    battery_sensor_attrs = battery_sensor.attributes
    assert battery_sensor.state == "89"
    assert battery_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Battery"
    assert battery_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_co2_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the co2 sensor for a WoTHPc."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:AA",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "hygrometer_co2",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 5

    battery_sensor = hass.states.get("sensor.test_name_battery")
    battery_sensor_attrs = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert battery_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Battery"
    assert battery_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    co2_sensor = hass.states.get("sensor.test_name_carbon_dioxide")
    co2_sensor_attrs = co2_sensor.attributes
    assert co2_sensor.state == "725"
    assert co2_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Carbon dioxide"
    assert co2_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "ppm"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_relay_switch_1pm_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the relay switch 1PM sensor."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WORELAY_SWITCH_1PM_SERVICE_INFO)

    with patch(
        "homeassistant.components.switchbot.switch.switchbot.SwitchbotRelaySwitch.get_basic_info",
        new=AsyncMock(
            return_value={
                "power": 4.9,
                "current": 0.02,
                "voltage": 25,
                "energy": 0.2,
            }
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: "relay_switch_1pm",
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
            unique_id="aabbccddeeaa",
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 5

    power_sensor = hass.states.get("sensor.test_name_power")
    power_sensor_attrs = power_sensor.attributes
    assert power_sensor.state == "4.9"
    assert power_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Power"
    assert power_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "W"
    assert power_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    voltage_sensor = hass.states.get("sensor.test_name_voltage")
    voltage_sensor_attrs = voltage_sensor.attributes
    assert voltage_sensor.state == "25"
    assert voltage_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Voltage"
    assert voltage_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert voltage_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    current_sensor = hass.states.get("sensor.test_name_current")
    current_sensor_attrs = current_sensor.attributes
    assert current_sensor.state == "0.02"
    assert current_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Current"
    assert current_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "A"
    assert current_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    energy_sensor = hass.states.get("sensor.test_name_energy")
    energy_sensor_attrs = energy_sensor.attributes
    assert energy_sensor.state == "0.2"
    assert energy_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Energy"
    assert energy_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "kWh"
    assert energy_sensor_attrs[ATTR_STATE_CLASS] == "total_increasing"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"
    assert rssi_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_leak_sensor(hass: HomeAssistant) -> None:
    """Test setting up the leak detector."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, LEAK_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "leak",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get("sensor.test_name_battery")
    battery_sensor_attrs = battery_sensor.attributes
    assert battery_sensor.state == "86"
    assert battery_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Battery"
    assert battery_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    leak_sensor = hass.states.get("binary_sensor.test_name")
    leak_sensor_attrs = leak_sensor.attributes
    assert leak_sensor.state == "off"
    assert leak_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remote(hass: HomeAssistant) -> None:
    """Test setting up the remote sensor."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, REMOTE_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "remote",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 2

    battery_sensor = hass.states.get("sensor.test_name_battery")
    battery_sensor_attrs = battery_sensor.attributes
    assert battery_sensor.state == "86"
    assert battery_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Battery"
    assert battery_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hub2_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the sensor for WoHub2."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOHUB2_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "hub2",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 5

    temperature_sensor = hass.states.get("sensor.test_name_temperature")
    temperature_sensor_attrs = temperature_sensor.attributes
    assert temperature_sensor.state == "26.4"
    assert temperature_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Temperature"
    assert temperature_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temperature_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humidity_sensor = hass.states.get("sensor.test_name_humidity")
    humidity_sensor_attrs = humidity_sensor.attributes
    assert humidity_sensor.state == "44"
    assert humidity_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Humidity"
    assert humidity_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humidity_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    light_level_sensor = hass.states.get("sensor.test_name_light_level")
    light_level_sensor_attrs = light_level_sensor.attributes
    assert light_level_sensor.state == "4"
    assert light_level_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Light level"

    illuminance_sensor = hass.states.get("sensor.test_name_illuminance")
    illuminance_sensor_attrs = illuminance_sensor.attributes
    assert illuminance_sensor.state == "30"
    assert illuminance_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Illuminance"
    assert illuminance_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hubmini_matter_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the sensor for HubMini Matter."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, HUBMINI_MATTER_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "hubmini_matter",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 3

    temperature_sensor = hass.states.get("sensor.test_name_temperature")
    temperature_sensor_attrs = temperature_sensor.attributes
    assert temperature_sensor.state == "24.1"
    assert temperature_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Temperature"
    assert temperature_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temperature_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humidity_sensor = hass.states.get("sensor.test_name_humidity")
    humidity_sensor_attrs = humidity_sensor.attributes
    assert humidity_sensor.state == "53"
    assert humidity_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Humidity"
    assert humidity_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humidity_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fan_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, CIRCULATOR_FAN_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "circulator_fan",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.update",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all("sensor")) == 2

        battery_sensor = hass.states.get("sensor.test_name_battery")
        battery_sensor_attrs = battery_sensor.attributes
        assert battery_sensor.state == "82"
        assert battery_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Battery"
        assert battery_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
        assert battery_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

        rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
        rssi_sensor_attrs = rssi_sensor.attributes
        assert rssi_sensor.state == "-60"
        assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
        assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hub3_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the sensor for Hub3."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, HUB3_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "hub3",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 5

    temperature_sensor = hass.states.get("sensor.test_name_temperature")
    temperature_sensor_attrs = temperature_sensor.attributes
    assert temperature_sensor.state == "25.3"
    assert temperature_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Temperature"
    assert temperature_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temperature_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humidity_sensor = hass.states.get("sensor.test_name_humidity")
    humidity_sensor_attrs = humidity_sensor.attributes
    assert humidity_sensor.state == "52"
    assert humidity_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Humidity"
    assert humidity_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humidity_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

    light_level_sensor = hass.states.get("sensor.test_name_light_level")
    light_level_sensor_attrs = light_level_sensor.attributes
    assert light_level_sensor.state == "3"
    assert light_level_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Light level"
    assert light_level_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    illuminance_sensor = hass.states.get("sensor.test_name_illuminance")
    illuminance_sensor_attrs = illuminance_sensor.attributes
    assert illuminance_sensor.state == "90"
    assert illuminance_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Illuminance"
    assert illuminance_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert illuminance_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_evaporative_humidifier_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the sensor for evaporative humidifier."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, EVAPORATIVE_HUMIDIFIER_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "evaporative_humidifier",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotEvaporativeHumidifier.update",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all("sensor")) == 4

        rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
        rssi_sensor_attrs = rssi_sensor.attributes
        assert rssi_sensor.state == "-60"
        assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
        assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"

        humidity_sensor = hass.states.get("sensor.test_name_humidity")
        humidity_sensor_attrs = humidity_sensor.attributes
        assert humidity_sensor.state == "53"
        assert humidity_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Humidity"
        assert humidity_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
        assert humidity_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

        temperature_sensor = hass.states.get("sensor.test_name_temperature")
        temperature_sensor_attrs = temperature_sensor.attributes
        assert temperature_sensor.state == "25.1"
        assert temperature_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Temperature"
        assert temperature_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
        assert temperature_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

        water_level_sensor = hass.states.get("sensor.test_name_water_level")
        water_level_sensor_attrs = water_level_sensor.attributes
        assert water_level_sensor.state == "medium"
        assert water_level_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Water level"
        assert water_level_sensor_attrs[ATTR_DEVICE_CLASS] == "enum"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_relay_switch_2pm_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the relay switch 2PM sensor."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, RELAY_SWITCH_2PM_SERVICE_INFO)

    with patch(
        "homeassistant.components.switchbot.switch.switchbot.SwitchbotRelaySwitch2PM.get_basic_info",
        new=AsyncMock(
            return_value={
                1: {
                    "power": 4.9,
                    "current": 0.1,
                    "voltage": 25,
                    "energy": 0.2,
                },
                2: {
                    "power": 7.9,
                    "current": 0.6,
                    "voltage": 25,
                    "energy": 2.5,
                },
            }
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: "relay_switch_2pm",
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
            unique_id="aabbccddeeaa",
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 9

    power_sensor_1 = hass.states.get("sensor.test_name_power_1")
    power_sensor_attrs = power_sensor_1.attributes
    assert power_sensor_1.state == "4.9"
    assert power_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name power 1"
    assert power_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "W"
    assert power_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    voltage_sensor_1 = hass.states.get("sensor.test_name_voltage_1")
    voltage_sensor_1_attrs = voltage_sensor_1.attributes
    assert voltage_sensor_1.state == "25"
    assert voltage_sensor_1_attrs[ATTR_FRIENDLY_NAME] == "test-name voltage 1"
    assert voltage_sensor_1_attrs[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert voltage_sensor_1_attrs[ATTR_STATE_CLASS] == "measurement"

    current_sensor_1 = hass.states.get("sensor.test_name_current_1")
    current_sensor_1_attrs = current_sensor_1.attributes
    assert current_sensor_1.state == "0.1"
    assert current_sensor_1_attrs[ATTR_FRIENDLY_NAME] == "test-name current 1"
    assert current_sensor_1_attrs[ATTR_UNIT_OF_MEASUREMENT] == "A"
    assert current_sensor_1_attrs[ATTR_STATE_CLASS] == "measurement"

    energy_sensor_1 = hass.states.get("sensor.test_name_energy_1")
    energy_sensor_1_attrs = energy_sensor_1.attributes
    assert energy_sensor_1.state == "0.2"
    assert energy_sensor_1_attrs[ATTR_FRIENDLY_NAME] == "test-name energy 1"
    assert energy_sensor_1_attrs[ATTR_UNIT_OF_MEASUREMENT] == "kWh"
    assert energy_sensor_1_attrs[ATTR_STATE_CLASS] == "total_increasing"

    power_sensor_2 = hass.states.get("sensor.test_name_power_2")
    power_sensor_2_attrs = power_sensor_2.attributes
    assert power_sensor_2.state == "7.9"
    assert power_sensor_2_attrs[ATTR_FRIENDLY_NAME] == "test-name power 2"
    assert power_sensor_2_attrs[ATTR_UNIT_OF_MEASUREMENT] == "W"
    assert power_sensor_2_attrs[ATTR_STATE_CLASS] == "measurement"

    voltage_sensor_2 = hass.states.get("sensor.test_name_voltage_2")
    voltage_sensor_2_attrs = voltage_sensor_2.attributes
    assert voltage_sensor_2.state == "25"
    assert voltage_sensor_2_attrs[ATTR_FRIENDLY_NAME] == "test-name voltage 2"
    assert voltage_sensor_2_attrs[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert voltage_sensor_2_attrs[ATTR_STATE_CLASS] == "measurement"

    current_sensor_2 = hass.states.get("sensor.test_name_current_2")
    current_sensor_2_attrs = current_sensor_2.attributes
    assert current_sensor_2.state == "0.6"
    assert current_sensor_2_attrs[ATTR_FRIENDLY_NAME] == "test-name current 2"
    assert current_sensor_2_attrs[ATTR_UNIT_OF_MEASUREMENT] == "A"
    assert current_sensor_2_attrs[ATTR_STATE_CLASS] == "measurement"

    energy_sensor_2 = hass.states.get("sensor.test_name_energy_2")
    energy_sensor_2_attrs = energy_sensor_2.attributes
    assert energy_sensor_2.state == "2.5"
    assert energy_sensor_2_attrs[ATTR_FRIENDLY_NAME] == "test-name energy 2"
    assert energy_sensor_2_attrs[ATTR_UNIT_OF_MEASUREMENT] == "kWh"
    assert energy_sensor_2_attrs[ATTR_STATE_CLASS] == "total_increasing"

    rssi_sensor = hass.states.get("sensor.test_name_bluetooth_signal")
    rssi_sensor_attrs = rssi_sensor.attributes
    assert rssi_sensor.state == "-60"
    assert rssi_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Bluetooth signal"
    assert rssi_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "dBm"
    assert rssi_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
