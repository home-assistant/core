"""Test the switchbot sensors."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    CIRCULATOR_FAN_SERVICE_INFO,
    WORELAY_SWITCH_1PM_SERVICE_INFO,
    setup_integration,
    snapshot_switchbot_entities,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Switchbot entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_relay_switch_1pm_power_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the power sensor."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WORELAY_SWITCH_1PM_SERVICE_INFO)

    with patch(
        "switchbot.SwitchbotRelaySwitch.update",
        return_value=None,
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

    power_sensor = hass.states.get("sensor.test_name_power")
    power_sensor_attrs = power_sensor.attributes
    assert power_sensor.state == "4.9"
    assert power_sensor_attrs[ATTR_FRIENDLY_NAME] == "test-name Power"
    assert power_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "W"

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
