"""Tests for TP-Link Omada sensor entities."""

from datetime import timedelta
import json
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import OmadaGatewayPortStatus, OmadaListDevice

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import POLL_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES + 10)


async def test_device_connected_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a connection status is reported."""
    entity = hass.states.get("sensor.test_poe_switch_device_status")
    assert entity is not None
    assert entity == snapshot


async def test_device_cpu_usage(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a CPU usage is reported correctly."""
    entity = hass.states.get("sensor.test_router_cpu_usage")
    assert entity is not None
    assert entity.state == "16"
    assert entity == snapshot


async def test_device_mem_usage(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a Memory usage is reported correctly."""
    entity = hass.states.get("sensor.test_poe_switch_memory_usage")
    assert entity is not None
    assert entity.state == "20"
    assert entity == snapshot


async def test_device_specific_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test a connection status is reported from known detailed status."""
    entity_id = "sensor.test_poe_switch_device_status"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "connected"

    _set_test_device_status(
        mock_omada_site_client,
        DeviceStatus.ADOPT_FAILED.value,
        DeviceStatusCategory.CONNECTED.value,
    )

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "adopt_failed"


async def test_device_category_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test a connection status is reported, with fallback to status category."""
    entity_id = "sensor.test_poe_switch_device_status"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "connected"

    _set_test_device_status(
        mock_omada_site_client,
        DeviceStatus.PENDING_WIRELESS,
        DeviceStatusCategory.PENDING.value,
    )

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "pending"


def _set_test_device_status(
    mock_omada_site_client: MagicMock,
    status: int,
    status_category: int,
) -> OmadaGatewayPortStatus:
    devices_data = json.loads(load_fixture("devices.json", DOMAIN))
    devices_data[1]["status"] = status
    devices_data[1]["statusCategory"] = status_category
    devices = [OmadaListDevice(d) for d in devices_data]

    mock_omada_site_client.get_devices.reset_mock()
    mock_omada_site_client.get_devices.return_value = devices
