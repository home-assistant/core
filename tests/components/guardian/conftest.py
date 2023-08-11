"""Define fixtures for Elexa Guardian tests."""
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.guardian import CONF_UID, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.guardian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={CONF_UID: "3456", **config},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PORT: 7777,
    }


@pytest.fixture(name="data_sensor_pair_dump", scope="package")
def data_sensor_pair_dump_fixture():
    """Define data from a successful sensor_pair_dump response."""
    return json.loads(load_fixture("sensor_pair_dump_data.json", "guardian"))


@pytest.fixture(name="data_sensor_pair_sensor", scope="package")
def data_sensor_pair_sensor_fixture():
    """Define data from a successful sensor_pair_sensor response."""
    return json.loads(load_fixture("sensor_pair_sensor_data.json", "guardian"))


@pytest.fixture(name="data_sensor_paired_sensor_status", scope="package")
def data_sensor_paired_sensor_status_fixture():
    """Define data from a successful sensor_paired_sensor_status response."""
    return json.loads(load_fixture("sensor_paired_sensor_status_data.json", "guardian"))


@pytest.fixture(name="data_system_diagnostics", scope="package")
def data_system_diagnostics_fixture():
    """Define data from a successful system_diagnostics response."""
    return json.loads(load_fixture("system_diagnostics_data.json", "guardian"))


@pytest.fixture(name="data_system_onboard_sensor_status", scope="package")
def data_system_onboard_sensor_status_fixture():
    """Define data from a successful system_onboard_sensor_status response."""
    return json.loads(
        load_fixture("system_onboard_sensor_status_data.json", "guardian")
    )


@pytest.fixture(name="data_system_ping", scope="package")
def data_system_ping_fixture():
    """Define data from a successful system_ping response."""
    return json.loads(load_fixture("system_ping_data.json", "guardian"))


@pytest.fixture(name="data_valve_status", scope="package")
def data_valve_status_fixture():
    """Define data from a successful valve_status response."""
    return json.loads(load_fixture("valve_status_data.json", "guardian"))


@pytest.fixture(name="data_wifi_status", scope="package")
def data_wifi_status_fixture():
    """Define data from a successful wifi_status response."""
    return json.loads(load_fixture("wifi_status_data.json", "guardian"))


@pytest.fixture(name="setup_guardian")
async def setup_guardian_fixture(
    hass,
    config,
    data_sensor_pair_dump,
    data_sensor_pair_sensor,
    data_sensor_paired_sensor_status,
    data_system_diagnostics,
    data_system_onboard_sensor_status,
    data_system_ping,
    data_valve_status,
    data_wifi_status,
):
    """Define a fixture to set up Guardian."""
    with patch("aioguardian.client.Client.connect"), patch(
        "aioguardian.commands.sensor.SensorCommands.pair_dump",
        return_value=data_sensor_pair_dump,
    ), patch(
        "aioguardian.commands.sensor.SensorCommands.pair_sensor",
        return_value=data_sensor_pair_sensor,
    ), patch(
        "aioguardian.commands.sensor.SensorCommands.paired_sensor_status",
        return_value=data_sensor_paired_sensor_status,
    ), patch(
        "aioguardian.commands.system.SystemCommands.diagnostics",
        return_value=data_system_diagnostics,
    ), patch(
        "aioguardian.commands.system.SystemCommands.onboard_sensor_status",
        return_value=data_system_onboard_sensor_status,
    ), patch(
        "aioguardian.commands.system.SystemCommands.ping",
        return_value=data_system_ping,
    ), patch(
        "aioguardian.commands.valve.ValveCommands.status",
        return_value=data_valve_status,
    ), patch(
        "aioguardian.commands.wifi.WiFiCommands.status",
        return_value=data_wifi_status,
    ), patch(
        "aioguardian.client.Client.disconnect"
    ), patch(
        "homeassistant.components.guardian.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "guardian_3456"
