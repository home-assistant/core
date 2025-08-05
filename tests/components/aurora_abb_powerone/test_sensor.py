"""Test the Aurora ABB PowerOne Solar PV sensors."""

from unittest.mock import patch

from aurorapy.client import AuroraError, AuroraTimeoutError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntryDisabler

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_CONFIG = {
    "sensor": {
        "platform": "aurora_abb_powerone",
        "device": "/dev/fakedevice0",
        "address": 2,
    }
}


def _simulated_returns(index, global_measure=None):
    returns = {
        1: 235.9476,  # voltage
        2: 2.7894,  # current
        3: 45.678,  # power
        4: 50.789,  # frequency
        6: 1.2345,  # leak dcdc
        7: 2.3456,  # leak inverter
        21: 9.876,  # temperature
        30: 0.1234,  # Isolation resistance
        5: 12345,  # energy
    }
    return returns[index]


def _mock_config_entry():
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            CONF_PORT: "/dev/usb999",
            CONF_ADDRESS: 3,
            ATTR_DEVICE_NAME: "mydevicename",
            ATTR_MODEL: "mymodel",
            ATTR_SERIAL_NUMBER: "123456",
            ATTR_FIRMWARE: "1.2.3.4",
        },
        source="dummysource",
        entry_id="13579",
        unique_id="654321",
    )


async def test_sensors(hass: HomeAssistant, entity_registry: EntityRegistry) -> None:
    """Test data coming back from inverter."""
    mock_entry = _mock_config_entry()

    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure",
            side_effect=_simulated_returns,
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
        patch(
            "aurorapy.client.AuroraSerialClient.serial_number",
            return_value="9876543",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.version",
            return_value="9.8.7.6",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.pn",
            return_value="A.B.C",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.firmware",
            return_value="1.234",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=_simulated_returns,
        ),
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.mydevicename_power_output")
        assert power
        assert power.state == "45.7"

        temperature = hass.states.get("sensor.mydevicename_temperature")
        assert temperature
        assert temperature.state == "9.9"

        energy = hass.states.get("sensor.mydevicename_total_energy")
        assert energy
        assert energy.state == "12.35"

        # Test the 'disabled by default' sensors.
        sensors = [
            ("sensor.mydevicename_grid_voltage", "235.9"),
            ("sensor.mydevicename_grid_current", "2.8"),
            ("sensor.mydevicename_frequency", "50.8"),
            ("sensor.mydevicename_dc_dc_leak_current", "1.2345"),
            ("sensor.mydevicename_inverter_leak_current", "2.3456"),
            ("sensor.mydevicename_isolation_resistance", "0.1234"),
        ]
        for entity_id, _ in sensors:
            assert not hass.states.get(entity_id)
            assert (entry := entity_registry.async_get(entity_id)), (
                f"Entity registry entry for {entity_id} is missing"
            )
            assert entry.disabled
            assert entry.disabled_by is RegistryEntryDisabler.INTEGRATION

            # re-enable it
            entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

        # must reload the integration when enabling an entity
        await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.NOT_LOADED
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        for entity_id, value in sensors:
            item = hass.states.get(entity_id)
            assert item
            assert item.state == value


async def test_sensor_dark(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test that darkness (no comms) is handled correctly."""
    mock_entry = _mock_config_entry()

    # sun is up
    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure", side_effect=_simulated_returns
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=_simulated_returns,
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.serial_number",
            return_value="9876543",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.version",
            return_value="9.8.7.6",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.pn",
            return_value="A.B.C",
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.firmware",
            return_value="1.234",
        ),
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.mydevicename_power_output")
        assert power is not None
        assert power.state == "45.7"

    # sunset
    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure",
            side_effect=AuroraTimeoutError("No response after 10 seconds"),
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=AuroraTimeoutError("No response after 3 tries"),
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
    ):
        freezer.tick(SCAN_INTERVAL * 2)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        power = hass.states.get("sensor.mydevicename_total_energy")
        assert power.state == "unknown"
    # sun rose again
    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure", side_effect=_simulated_returns
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=_simulated_returns,
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
    ):
        freezer.tick(SCAN_INTERVAL * 4)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        power = hass.states.get("sensor.mydevicename_power_output")
        assert power is not None
        assert power.state == "45.7"
    # sunset
    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure",
            side_effect=AuroraTimeoutError("No response after 10 seconds"),
        ),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=AuroraError("No response after 10 seconds"),
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
    ):
        freezer.tick(SCAN_INTERVAL * 6)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        power = hass.states.get("sensor.mydevicename_power_output")
        assert power.state == "unknown"  # should this be 'available'?


async def test_sensor_unknown_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test other comms error is handled correctly."""
    mock_entry = _mock_config_entry()

    # sun is up
    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure", side_effect=_simulated_returns
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
        patch(
            "aurorapy.client.AuroraSerialClient.cumulated_energy",
            side_effect=_simulated_returns,
        ),
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.measure",
            side_effect=AuroraError("another error"),
        ),
        patch("aurorapy.client.AuroraSerialClient.alarms", return_value=["No alarm"]),
        patch("serial.Serial.isOpen", return_value=True),
    ):
        freezer.tick(SCAN_INTERVAL * 2)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert (
            "Exception: AuroraError('another error') occurred, 2 retries remaining"
            in caplog.text
        )
        power = hass.states.get("sensor.mydevicename_power_output")
        assert power.state == "unavailable"
