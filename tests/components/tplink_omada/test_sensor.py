"""Tests for TP-Link Omada sensor entities."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client import OmadaControllerInfo
from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.tplink_omada.config_flow import CONF_SITE
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import POLL_DEVICES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
    snapshot_platform,
)

POLL_INTERVAL = timedelta(seconds=POLL_DEVICES)


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


@pytest.mark.usefixtures("mock_omada_client")
async def test_controller_entities_created_once_per_controller(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test controller entities are only created for one site config entry."""
    second_entry = MockConfigEntry(
        title="Test Omada Controller (Second)",
        domain=DOMAIN,
        data={**mock_config_entry.data, CONF_SITE: "Second"},
        unique_id="12345_Second",
        version=2,
    )

    mock_config_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    with patch("homeassistant.components.tplink_omada.PLATFORMS", ["sensor"]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED

    controller_entity_ids = sorted(
        state.entity_id
        for state in hass.states.async_all(SENSOR_DOMAIN)
        if state.entity_id.startswith("sensor.omada_controller")
    )
    assert controller_entity_ids == [
        "sensor.omada_controller_api_version",
        "sensor.omada_controller_device_status",
        "sensor.omada_controller_version",
    ]

    for unique_id in (
        "2b8ebfe7af51afa2f58844e1f9ba0c04_api_version",
        "2b8ebfe7af51afa2f58844e1f9ba0c04_device_status",
        "2b8ebfe7af51afa2f58844e1f9ba0c04_version",
    ):
        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, unique_id
        )
        assert entity_id is not None
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.config_entry_id == mock_config_entry.entry_id


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


async def test_controller_status_connected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test controller status reports connected."""
    entity = _get_controller_status_state(hass)

    assert entity.state == "connected"
    assert entity.attributes["configured"] is True
    assert entity.attributes["type"] == 1
    assert entity.attributes["support_app"] is True
    assert "omadac_id" not in entity.attributes
    assert entity.attributes["registered_root"] is True
    assert entity.attributes["omadac_category"] == "advanced"
    assert entity.attributes["msp_mode"] is False
    assert entity.attributes["omada_cloud_url"] == "https://omada.tplinkcloud.com"

    version_entity = hass.states.get("sensor.omada_controller_version")
    assert version_entity is not None
    assert version_entity.state == "6.2.10.15"

    api_version_entity = hass.states.get("sensor.omada_controller_api_version")
    assert api_version_entity is not None
    assert api_version_entity.state == "3"


async def test_controller_status_disconnected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test controller status reports disconnected when it is not configured."""
    await _set_controller_configured(hass, mock_omada_client, False)

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = _get_controller_status_state(hass)
    assert entity.state == "disconnected"
    assert entity.attributes["configured"] is False


async def test_controller_status_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test controller sensors are unavailable when controller info cannot update."""
    mock_omada_client.get_controller_info.side_effect = OmadaClientException()

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _get_controller_status_state(hass).state == STATE_UNAVAILABLE
    version_entity = hass.states.get("sensor.omada_controller_version")
    assert version_entity is not None
    assert version_entity.state == STATE_UNAVAILABLE

    api_version_entity = hass.states.get("sensor.omada_controller_api_version")
    assert api_version_entity is not None
    assert api_version_entity.state == STATE_UNAVAILABLE


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


def _get_controller_status_state(hass: HomeAssistant) -> State:
    entity = hass.states.get("sensor.omada_controller_device_status")
    assert entity is not None
    return entity


async def _set_controller_configured(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    configured: bool,
) -> None:
    controller_info_data = await async_load_json_object_fixture(
        hass, "controller-info.json", DOMAIN
    )
    controller_info_data["configured"] = configured
    mock_omada_client.get_controller_info.reset_mock()
    mock_omada_client.get_controller_info.return_value = OmadaControllerInfo(
        controller_info_data
    )


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
