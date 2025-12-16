"""Test the Aurora ABB PowerOne Solar PV sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraClientError,
    AuroraClientTimeoutError,
    AuroraInverterData,
    AuroraInverterIdentifier,
)
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    SCAN_INTERVAL,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntryDisabler

from tests.common import MockConfigEntry, async_fire_time_changed


@dataclass
class _FakeClient:
    """Duck-typed stand-in for AuroraClient instance kept by the coordinator."""

    mode: Literal["ok", "timeout", "error"] = "ok"

    def try_connect_and_fetch_identifier(self) -> AuroraInverterIdentifier:
        return AuroraInverterIdentifier(
            serial_number="9876543",
            model="9.8.7.6 (A.B.C)",
            firmware="1.234",
        )

    def try_connect_and_fetch_data(self) -> AuroraInverterData:
        if self.mode == "timeout":
            raise AuroraClientTimeoutError("No response after 10 seconds")
        if self.mode == "error":
            raise AuroraClientError("another error")

        return AuroraInverterData(
            grid_voltage=235.9,
            grid_current=2.8,
            instantaneouspower=45.7,
            grid_frequency=50.8,
            i_leak_dcdc=1.2345,
            i_leak_inverter=2.3456,
            temp=9.9,
            r_iso=0.1234,
            totalenergy=12.35,
            alarm="No alarm",
        )


def _mock_config_entry_serial():
    return MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_SERIAL_COMPORT: "/dev/usb999",
            CONF_INVERTER_SERIAL_ADDRESS: 2,
            ATTR_DEVICE_NAME: "mydevicename",
            ATTR_MODEL: "mymodel",
            ATTR_SERIAL_NUMBER: "123456",
            ATTR_FIRMWARE: "1.2.3.4",
        },
        source="dummysource",
        entry_id="13579",
        unique_id="654321",
    )


def _mock_config_entry_tcp():
    return MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            CONF_TRANSPORT: TRANSPORT_TCP,
            CONF_TCP_HOST: "127.0.0.1",
            CONF_TCP_PORT: 8899,
            CONF_INVERTER_SERIAL_ADDRESS: 2,
            ATTR_DEVICE_NAME: "mydevicename",
            ATTR_MODEL: "mymodel",
            ATTR_SERIAL_NUMBER: "123456",
            ATTR_FIRMWARE: "1.2.3.4",
        },
        source="dummysource",
        entry_id="24680",
        unique_id="112233",
    )


async def test_sensors(hass: HomeAssistant, entity_registry: EntityRegistry) -> None:
    """Test data coming back from inverter (serial transport)."""
    mock_entry = _mock_config_entry_serial()
    fake_client = _FakeClient(mode="ok")

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=fake_client,
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
        entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.NOT_LOADED

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=fake_client,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    for entity_id, value in sensors:
        item = hass.states.get(entity_id)
        assert item
        assert item.state == value


async def test_sensor_dark(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test that darkness (no comms / timeout) is handled correctly."""
    mock_entry = _mock_config_entry_serial()
    fake_client = _FakeClient(mode="ok")

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=fake_client,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.mydevicename_power_output")
        assert power is not None
        assert power.state == "45.7"

    fake_client.mode = "timeout"
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    total = hass.states.get("sensor.mydevicename_total_energy")
    assert total is not None
    assert total.state == "unknown"

    fake_client.mode = "ok"
    freezer.tick(SCAN_INTERVAL * 4)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    power = hass.states.get("sensor.mydevicename_power_output")
    assert power is not None
    assert power.state == "45.7"

    fake_client.mode = "error"
    freezer.tick(SCAN_INTERVAL * 6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    power = hass.states.get("sensor.mydevicename_power_output")
    assert power.state == "unavailable"


async def test_sensor_unknown_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test other comms error is handled correctly (retries + log message)."""
    mock_entry = _mock_config_entry_serial()
    fake_client = _FakeClient(mode="ok")

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=fake_client,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    fake_client.mode = "error"
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "Exception: AuroraClientError('another error') occurred, 2 retries remaining"
        in caplog.text
    )
    power = hass.states.get("sensor.mydevicename_power_output")
    assert power.state == "unavailable"


async def test_tcp_transport_smoketest(hass: HomeAssistant) -> None:
    """Basic check that TCP transport path wires up and produces states."""
    mock_entry = _mock_config_entry_tcp()
    fake_client = _FakeClient(mode="ok")

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_tcp",
        return_value=fake_client,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    power = hass.states.get("sensor.mydevicename_power_output")
    assert power
    assert power.state == "45.7"
