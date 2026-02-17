"""Tests for TP-Link Omada sensor entities."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import OmadaListDevice

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import POLL_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    Generator,
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES)


@pytest.fixture(autouse=True)
def patch_binary_sensor_platforms() -> Generator[None]:
    """Patch PLATFORMS to only include binary_sensor for tests."""
    with patch("homeassistant.components.tplink_omada.PLATFORMS", ["binary_sensor"]):
        yield


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the TP-Link Omada binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_no_gateway_creates_no_port_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that if there is no gateway, no gateway port sensors are created."""

    await _remove_test_device(hass, mock_omada_site_client, 0)

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_omada_site_client.get_gateway.assert_not_called()


async def test_disconnected_device_sensor_not_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that if the gateway is not connected to the controller, gateway entities are not created."""

    await _set_test_device_status(
        hass,
        mock_omada_site_client,
        0,
        DeviceStatus.DISCONNECTED.value,
        DeviceStatusCategory.DISCONNECTED.value,
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.test_router_port_1_lan_status"
    entity = hass.states.get(entity_id)
    assert entity is None

    # "Connect" the gateway
    await _set_test_device_status(
        hass,
        mock_omada_site_client,
        0,
        DeviceStatus.CONNECTED.value,
        DeviceStatusCategory.CONNECTED.value,
    )

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == "off"

    mock_omada_site_client.get_gateway.assert_called_once_with("AA-BB-CC-DD-EE-FF")


async def _set_test_device_status(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    dev_index: int,
    status: int,
    status_category: int,
) -> None:
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    devices_data[dev_index]["status"] = status
    devices_data[dev_index]["statusCategory"] = status_category
    devices = [OmadaListDevice(d) for d in devices_data]

    mock_omada_site_client.get_devices.reset_mock()
    mock_omada_site_client.get_devices.return_value = devices


async def _remove_test_device(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    dev_index: int,
) -> None:
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    del devices_data[dev_index]
    devices = [OmadaListDevice(d) for d in devices_data]

    mock_omada_site_client.get_devices.reset_mock()
    mock_omada_site_client.get_devices.return_value = devices
