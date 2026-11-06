"""Tests for TP-Link Omada sensor entities."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import (
    OmadaListDevice,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    POLL_DEVICES,
    POLL_SWITCH_PORT,
    OmadaDevicesCoordinator,
    OmadaSwitchPortCoordinator,
)
from homeassistant.components.tplink_omada.sensor import (
    OMADA_DEVICE_SENSORS,
    OMADA_SWITCH_PORT_SENSORS,
    OmadaDeviceSensor,
    OmadaSwitchPortSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES)
PORT_POLL_INTERVAL = timedelta(seconds=POLL_SWITCH_PORT)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
) -> MockConfigEntry:
    """Set up the TP-Link Omada integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", ["sensor"]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the TP-Link Omada sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_device_specific_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a connection status is reported from known detailed status."""
    entity_id = "sensor.test_poe_switch_device_status"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "connected"

    await _set_test_device_status(
        hass,
        mock_omada_site_client,
        DeviceStatus.ADOPT_FAILED.value,
        DeviceStatusCategory.CONNECTED.value,
    )

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity and entity.state == "adopt_failed"


async def test_device_category_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a connection status is reported, with fallback to status category."""
    entity_id = "sensor.test_poe_switch_device_status"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "connected"

    await _set_test_device_status(
        hass,
        mock_omada_site_client,
        DeviceStatus.PENDING_WIRELESS.value,
        DeviceStatusCategory.PENDING.value,
    )

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity and entity.state == "pending"


async def test_poe_power_sensor_updates(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the PoE power sensor reports the latest polled value."""
    entity_id = "sensor.test_poe_switch_port_1_poe_power"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "2.7"

    ports_data = await async_load_json_array_fixture(
        hass, "switch-ports-TL-SG3210XHP-M2.json", DOMAIN
    )
    ports_data[0]["portStatus"]["poePower"] = 5.4
    mock_omada_site_client.get_switch_ports.return_value = [
        OmadaSwitchPortDetails(p) for p in ports_data
    ]

    freezer.tick(PORT_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity and entity.state == "5.4"


async def test_sfp_port_has_no_poe_power_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test SFP ports do not get a PoE power sensor."""
    assert hass.states.get("sensor.test_poe_switch_port_9_poe_power") is None
    assert hass.states.get("sensor.test_poe_switch_port_8_poe_power") is not None


async def test_port_disappearing_from_coordinator_becomes_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a port no longer reported by the switch makes its sensor unavailable."""
    entity_id = "sensor.test_poe_switch_port_1_poe_power"
    assert hass.states.get(entity_id).state == "2.7"

    # Firmware update or port reconfiguration: the port is no longer reported
    ports_data = await async_load_json_array_fixture(
        hass, "switch-ports-TL-SG3210XHP-M2.json", DOMAIN
    )
    mock_omada_site_client.get_switch_ports.return_value = [
        OmadaSwitchPortDetails(p) for p in ports_data if p.get("port") != 1
    ]

    with caplog.at_level(logging.ERROR):
        freezer.tick(PORT_POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # The sensor exists and becomes unavailable, without errors from the
    # switch port coordinator
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "unavailable"
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert not any("Omada API Data - Test PoE Switch Ports" in msg for msg in errors)


async def test_device_disappearing_from_coordinator_becomes_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device removed from the controller makes its sensors unavailable."""
    entity_id = "sensor.test_poe_switch_device_status"
    assert hass.states.get(entity_id).state == "connected"

    # The device is no longer returned by the controller
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    mock_omada_site_client.get_devices.return_value = [
        OmadaListDevice(d) for d in devices_data if d.get("mac") != "54-AF-97-00-00-01"
    ]

    with caplog.at_level(logging.ERROR):
        freezer.tick(POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # The sensor exists and becomes unavailable, without errors from the
    # device list coordinator (the update coordinator has its own separate
    # error handling for vanished devices and is out of scope here)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "unavailable"
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert not any("Omada API Data - DeviceList" in msg for msg in errors)


async def _set_test_device_status(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    status: int,
    status_category: int,
) -> None:
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    devices_data[1]["status"] = status
    devices_data[1]["statusCategory"] = status_category
    devices = [OmadaListDevice(d) for d in devices_data]

    mock_omada_site_client.get_devices.reset_mock()
    mock_omada_site_client.get_devices.return_value = devices


async def test_entities_created_while_key_missing_are_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test entities created before their key appears in coordinator data."""
    mock_config_entry.add_to_hass(hass)

    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    device = OmadaListDevice(devices_data[1])
    switch_data = await async_load_json_object_fixture(
        hass, "switch-TL-SG3210XHP-M2.json", DOMAIN
    )
    switch = OmadaSwitch(switch_data)
    ports_data = await async_load_json_array_fixture(
        hass, "switch-ports-TL-SG3210XHP-M2.json", DOMAIN
    )
    port = OmadaSwitchPortDetails(ports_data[0])

    devices_coordinator = OmadaDevicesCoordinator(
        hass, mock_config_entry, mock_omada_site_client
    )
    device_sensor = OmadaDeviceSensor(
        devices_coordinator, device, OMADA_DEVICE_SENSORS[0]
    )
    assert device_sensor.available is False

    port_coordinator = OmadaSwitchPortCoordinator(
        hass, mock_config_entry, mock_omada_site_client, switch
    )
    port_sensor = OmadaSwitchPortSensor(
        port_coordinator, switch, port, OMADA_SWITCH_PORT_SENSORS[0], "1"
    )
    assert port_sensor.available is False
