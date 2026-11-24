"""The tests for the Google Wifi sensor platform."""

from datetime import timedelta

import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.components.google_wifi.coordinator import GoogleWifiCoordinator
from homeassistant.components.google_wifi.sensor import SENSOR_TYPES, GoogleWifiSensor
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import mock_device, setup_integration
from .const import RESOURCE_URL, UPDATED_RESPONSE


async def fire_polling_update(hass: HomeAssistant, seconds: int) -> None:
    """Advance time far enough to trigger the coordinator update."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_success")
async def test_sensors_expose_router_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a config entry creates the router sensors."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.test_wifi_current_version").state == "softwareVersion"
    )
    assert hass.states.get("sensor.test_wifi_new_version").state == "Latest"
    assert hass.states.get("sensor.test_wifi_uptime").state == "1.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == "10.0.0.10"
    assert hass.states.get("sensor.test_wifi_status").state == "Online"
    assert hass.states.get("sensor.test_wifi_last_restart") is not None
    assert (
        hass.states.get("sensor.test_wifi_current_version").attributes[
            ATTR_FRIENDLY_NAME
        ]
        == "Test Wifi Current version"
    )
    assert (
        hass.states.get("sensor.test_wifi_new_version").attributes[ATTR_FRIENDLY_NAME]
        == "Test Wifi New version"
    )
    assert (
        hass.states.get("sensor.test_wifi_uptime").attributes[ATTR_FRIENDLY_NAME]
        == "Test Wifi Uptime"
    )
    assert (
        hass.states.get("sensor.test_wifi_local_ip").attributes[ATTR_FRIENDLY_NAME]
        == "Test Wifi Local IP"
    )
    assert (
        hass.states.get("sensor.test_wifi_status").attributes[ATTR_FRIENDLY_NAME]
        == "Test Wifi Status"
    )
    assert (
        hass.states.get("sensor.test_wifi_last_restart").attributes[ATTR_FRIENDLY_NAME]
        == "Test Wifi Last restart"
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Test Wifi"
    assert device.sw_version == "softwareVersion"


@pytest.mark.usefixtures("mock_success")
async def test_device_software_version_follows_firmware_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the device registry shows the firmware version after an update."""
    await setup_integration(hass, mock_config_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(RESOURCE_URL, json=UPDATED_RESPONSE)
    await fire_polling_update(hass, 31)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "newVersion"


@pytest.mark.usefixtures("mock_unreachable")
async def test_setup_retries_when_router_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup waits to retry when the router does not respond."""
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.test_wifi_uptime") is None


async def test_native_value_when_data_is_none(hass: HomeAssistant) -> None:
    """Test an unavailable entity has no native value."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Wifi",
        data={CONF_HOST: "192.168.86.1"},
    )
    coordinator = GoogleWifiCoordinator(hass, entry, api=None)

    sensor = GoogleWifiSensor(coordinator, SENSOR_TYPES[0])

    assert sensor.native_value is None


@pytest.mark.usefixtures("mock_success")
async def test_sensor_updates_after_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the sensors become unavailable on failure and recover on the next poll."""
    await setup_integration(hass, mock_config_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        RESOURCE_URL,
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    await fire_polling_update(hass, 31)
    assert hass.states.get("sensor.test_wifi_uptime").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_wifi_status").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(RESOURCE_URL, json=UPDATED_RESPONSE)
    await fire_polling_update(hass, 62)

    assert hass.states.get("sensor.test_wifi_current_version").state == "newVersion"
    assert hass.states.get("sensor.test_wifi_new_version").state == "1.2.3.4"
    assert hass.states.get("sensor.test_wifi_uptime").state == "2.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_wifi_status").state == "Offline"


async def test_multiple_devices(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each router address is its own device."""
    devices = (
        ("192.168.86.1", "Living Room"),
        ("192.168.86.2", "Office"),
        ("192.168.86.3", "Basement"),
    )
    entries: list[MockConfigEntry] = []
    for host, title in devices:
        mock_device(aioclient_mock, host)
        entry = MockConfigEntry(domain=DOMAIN, title=title, data={CONF_HOST: host})
        await setup_integration(hass, entry)
        entries.append(entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 3
    assert hass.states.get("sensor.living_room_status").state == "Online"
    assert hass.states.get("sensor.office_status").state == "Online"
    assert hass.states.get("sensor.basement_status").state == "Online"
    assert (
        hass.states.get("sensor.living_room_status").attributes[ATTR_FRIENDLY_NAME]
        == "Living Room Status"
    )
    assert (
        hass.states.get("sensor.office_status").attributes[ATTR_FRIENDLY_NAME]
        == "Office Status"
    )
    assert (
        hass.states.get("sensor.basement_status").attributes[ATTR_FRIENDLY_NAME]
        == "Basement Status"
    )
    office_entry = entries[1]
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, office_entry.entry_id), office_entry.entry_id
        )
        is not None
    )


@pytest.mark.usefixtures("mock_success")
async def test_yaml_import_creates_config_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test YAML sensor configuration is imported into a config entry."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": DOMAIN,
                CONF_NAME: "Test Wifi",
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Test Wifi"
    assert entries[0].data[CONF_HOST] == "192.168.86.1"
    assert hass.states.get("sensor.test_wifi_uptime").state == "1.0"
    issue = issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")
    assert issue is not None


async def test_yaml_import_supports_multiple_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test each YAML host is imported as its own config entry."""
    devices = (
        ("192.168.86.1", "Living Room"),
        ("192.168.86.2", "Office"),
        ("192.168.86.3", "Basement"),
    )
    for host, _title in devices:
        mock_device(aioclient_mock, host)

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": DOMAIN,
                    CONF_HOST: host,
                    CONF_NAME: title,
                }
                for host, title in devices
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 3
    assert {entry.data[CONF_HOST] for entry in entries} == {
        "192.168.86.1",
        "192.168.86.2",
        "192.168.86.3",
    }
    assert hass.states.get("sensor.living_room_local_ip") is not None
    assert hass.states.get("sensor.office_local_ip") is not None
    assert hass.states.get("sensor.basement_local_ip") is not None


async def test_yaml_import_duplicate_names_keep_legacy_entity_ids(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test devices sharing a YAML name get the suffixed entity IDs they had before."""
    mock_device(aioclient_mock, "192.168.86.1")
    mock_device(aioclient_mock, "192.168.86.2")

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {"platform": DOMAIN, CONF_HOST: "192.168.86.1"},
                {"platform": DOMAIN, CONF_HOST: "192.168.86.2"},
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.title for entry in entries] == ["google_wifi", "google_wifi"]
    assert hass.states.get("sensor.google_wifi_status") is not None
    assert hass.states.get("sensor.google_wifi_status_2") is not None


@pytest.mark.usefixtures("mock_unreachable")
async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed YAML import explains why the device was not added."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": DOMAIN}},
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
