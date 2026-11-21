"""Tests for read-only LAN/VLAN sensors."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from tplink_omada_client.exceptions import OmadaClientException
from tplink_omada_client.networks import LanNetwork

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "sensor.oc200_test_omada_controller_vlan_office"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    with patch("homeassistant.components.tplink_omada.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_omada_client")
@pytest.mark.parametrize(
    ("optional", "expected_state", "expected_attributes", "expected_name"),
    [
        pytest.param(
            {
                "vlan": 10,
                "gatewaySubnet": "192.0.2.1/24",
                "dhcpSettings": {"enable": True},
            },
            "10",
            {"gateway_subnet": "192.0.2.1/24", "dhcp_enabled": True},
            "VLAN Office",
            id="complete",
        ),
        pytest.param(
            {"vlan": 20, "dhcpSettings": {"enable": False}},
            "20",
            {"dhcp_enabled": False},
            "VLAN Office",
            id="dhcp_disabled",
        ),
        pytest.param({}, STATE_UNKNOWN, {}, "LAN Office", id="plain_lan"),
        pytest.param(
            {"vlan": None, "gatewaySubnet": None, "dhcpSettings": None},
            STATE_UNKNOWN,
            {},
            "LAN Office",
            id="null_fields",
        ),
        pytest.param(
            {"vlan": 1, "dhcpSettings": {}}, "1", {}, "VLAN Office", id="dhcp_unknown"
        ),
    ],
)
async def test_network_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    entity_registry: er.EntityRegistry,
    optional: dict,
    expected_state: str,
    expected_attributes: dict,
    expected_name: str,
) -> None:
    """Report optional fields and associate the sensor with the controller."""
    mock_omada_site_client.get_lan_networks.return_value = [
        LanNetwork(
            {"id": "network-a", "name": "Office", "purpose": "interface", **optional}
        )
    ]
    await _setup(hass, mock_config_entry)
    entity_id = "sensor.oc200_test_omada_controller_" + expected_name.lower().replace(
        " ", "_"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes == {
        "friendly_name": f"OC200 - Test Omada Controller {expected_name}",
        "network_id": "network-a",
        "network_name": "Office",
        "purpose": "interface",
        **expected_attributes,
    }
    sensor_entry = entity_registry.async_get(entity_id)
    controller_entry = entity_registry.async_get(
        "sensor.oc200_test_omada_controller_device_status"
    )
    assert sensor_entry is not None
    assert controller_entry is not None
    assert sensor_entry.device_id == controller_entry.device_id
    assert sensor_entry.entity_category is None
    mock_omada_site_client.get_lan_networks.assert_awaited_once()


@pytest.mark.usefixtures("mock_omada_client")
async def test_network_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Discover networks, preserve identity on rename and recover from failures."""
    mock_omada_site_client.get_lan_networks.return_value = [
        LanNetwork({"id": "network-a", "name": "Office", "purpose": "vlan", "vlan": 10})
    ]
    await _setup(hass, mock_config_entry)
    unique_id = entity_registry.async_get(ENTITY_ID).unique_id
    mock_omada_site_client.get_lan_networks.return_value = [
        LanNetwork(
            {"id": "network-a", "name": "Renamed", "purpose": "vlan", "vlan": 20}
        ),
        LanNetwork({"id": "network-b", "name": "IoT", "purpose": "vlan", "vlan": 30}),
    ]
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "20"
    assert (
        hass.states.get(ENTITY_ID).attributes["friendly_name"]
        == "OC200 - Test Omada Controller VLAN Renamed"
    )
    assert entity_registry.async_get(ENTITY_ID).unique_id == unique_id
    assert hass.states.get("sensor.oc200_test_omada_controller_vlan_iot").state == "30"

    mock_omada_site_client.get_lan_networks.side_effect = OmadaClientException(
        "LAN unavailable"
    )
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert (
        hass.states.get("sensor.oc200_test_omada_controller_device_status").state
        == "connected"
    )

    mock_omada_site_client.get_lan_networks.side_effect = None
    mock_omada_site_client.get_lan_networks.return_value = []
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_omada_site_client.get_lan_networks.return_value = [
        LanNetwork({"id": "network-a", "name": "Office", "purpose": "vlan", "vlan": 10})
    ]
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "10"
    assert entity_registry.async_get(ENTITY_ID).unique_id == unique_id


@pytest.mark.usefixtures("mock_omada_client")
async def test_initial_network_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retry LAN discovery without blocking existing sensors."""
    mock_omada_site_client.get_lan_networks.side_effect = OmadaClientException(
        "LAN unavailable"
    )
    await _setup(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.oc200_test_omada_controller_device_status").state
        == "connected"
    )
    assert hass.states.get(ENTITY_ID) is None
    mock_omada_site_client.get_lan_networks.side_effect = None
    mock_omada_site_client.get_lan_networks.return_value = [
        LanNetwork({"id": "network-a", "name": "Office", "purpose": "vlan", "vlan": 10})
    ]
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "10"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    calls = mock_omada_site_client.get_lan_networks.await_count
    freezer.tick(timedelta(seconds=601))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_omada_site_client.get_lan_networks.await_count == calls
