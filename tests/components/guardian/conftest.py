"""Define fixtures for Elexa Guardian tests."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.guardian import CONF_UID, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.guardian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any], unique_id: str
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={CONF_UID: "3456", **config},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PORT: 7777,
    }


@pytest.fixture(name="data_sensor_pair_dump", scope="package")
def data_sensor_pair_dump_fixture() -> JsonObjectType:
    """Define data from a successful sensor_pair_dump response."""
    return load_json_object_fixture("sensor_pair_dump_data.json", "guardian")


@pytest.fixture(name="data_sensor_pair_sensor", scope="package")
def data_sensor_pair_sensor_fixture() -> JsonObjectType:
    """Define data from a successful sensor_pair_sensor response."""
    return load_json_object_fixture("sensor_pair_sensor_data.json", "guardian")


@pytest.fixture(name="data_sensor_paired_sensor_status", scope="package")
def data_sensor_paired_sensor_status_fixture() -> JsonObjectType:
    """Define data from a successful sensor_paired_sensor_status response."""
    return load_json_object_fixture("sensor_paired_sensor_status_data.json", "guardian")


@pytest.fixture(name="data_system_diagnostics", scope="package")
def data_system_diagnostics_fixture() -> JsonObjectType:
    """Define data from a successful system_diagnostics response."""
    return load_json_object_fixture("system_diagnostics_data.json", "guardian")


@pytest.fixture(name="data_system_onboard_sensor_status", scope="package")
def data_system_onboard_sensor_status_fixture() -> JsonObjectType:
    """Define data from a successful system_onboard_sensor_status response."""
    return load_json_object_fixture(
        "system_onboard_sensor_status_data.json", "guardian"
    )


@pytest.fixture(name="data_system_ping", scope="package")
def data_system_ping_fixture() -> JsonObjectType:
    """Define data from a successful system_ping response."""
    return load_json_object_fixture("system_ping_data.json", "guardian")


@pytest.fixture(name="data_valve_status", scope="package")
def data_valve_status_fixture() -> JsonObjectType:
    """Define data from a successful valve_status response."""
    return load_json_object_fixture("valve_status_data.json", "guardian")


@pytest.fixture(name="data_wifi_status", scope="package")
def data_wifi_status_fixture() -> JsonObjectType:
    """Define data from a successful wifi_status response."""
    return load_json_object_fixture("wifi_status_data.json", "guardian")


@pytest.fixture(name="setup_guardian")
async def setup_guardian_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    data_sensor_pair_dump: JsonObjectType,
    data_sensor_pair_sensor: JsonObjectType,
    data_sensor_paired_sensor_status: JsonObjectType,
    data_system_diagnostics: JsonObjectType,
    data_system_onboard_sensor_status: JsonObjectType,
    data_system_ping: JsonObjectType,
    data_valve_status: JsonObjectType,
    data_wifi_status: JsonObjectType,
) -> AsyncGenerator[None]:
    """Define a fixture to set up Guardian."""
    with (
        patch("aioguardian.client.Client.connect"),
        patch(
            "aioguardian.commands.sensor.SensorCommands.pair_dump",
            return_value=data_sensor_pair_dump,
        ),
        patch(
            "aioguardian.commands.sensor.SensorCommands.pair_sensor",
            return_value=data_sensor_pair_sensor,
        ),
        patch(
            "aioguardian.commands.sensor.SensorCommands.paired_sensor_status",
            return_value=data_sensor_paired_sensor_status,
        ),
        patch(
            "aioguardian.commands.system.SystemCommands.diagnostics",
            return_value=data_system_diagnostics,
        ),
        patch(
            "aioguardian.commands.system.SystemCommands.onboard_sensor_status",
            return_value=data_system_onboard_sensor_status,
        ),
        patch(
            "aioguardian.commands.system.SystemCommands.ping",
            return_value=data_system_ping,
        ),
        patch(
            "aioguardian.commands.valve.ValveCommands.status",
            return_value=data_valve_status,
        ),
        patch(
            "aioguardian.commands.wifi.WiFiCommands.status",
            return_value=data_wifi_status,
        ),
        patch(
            "aioguardian.client.Client.disconnect",
        ),
        patch(
            "homeassistant.components.guardian.PLATFORMS",
            [],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture() -> str:
    """Define a config entry unique ID fixture."""
    return "guardian_3456"
