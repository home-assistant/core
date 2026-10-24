"""The tests the for Meraki device tracker."""

from http import HTTPStatus
import json
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import legacy
from homeassistant.components.meraki.const import CONF_ORGANIZATION_ID, DOMAIN
from homeassistant.components.meraki.coordinator import UPDATE_INTERVAL
from homeassistant.components.meraki.device_tracker import (
    CONF_SECRET,
    CONF_VALIDATOR,
    URL,
)
from homeassistant.const import (
    CONF_PLATFORM,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import api_error, setup_integration
from .conftest import ORGANIZATION_ID

PHONE = "device_tracker.pixel_9"


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator poll the API again."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
async def meraki_client(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> TestClient:
    """Meraki mock client."""
    assert await async_setup_component(
        hass,
        device_tracker.DOMAIN,
        {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: "meraki",
                CONF_VALIDATOR: "validator",
                CONF_SECRET: "secret",
            }
        },
    )
    await hass.async_block_till_done()

    return await hass_client()


@pytest.mark.usefixtures("meraki_client")
async def test_cmx_deprecated(issue_registry: ir.IssueRegistry) -> None:
    """Test setting up the CMX location service in YAML raises a repair issue."""
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_cmx")
    assert issue.breaks_in_ha_version == "2027.5.0"


async def test_invalid_or_missing_data(
    mock_device_tracker_conf: list[legacy.Device], meraki_client
) -> None:
    """Test validator with invalid or missing data."""
    req = await meraki_client.get(URL)
    text = await req.text()
    assert req.status == HTTPStatus.OK
    assert text == "validator"

    req = await meraki_client.post(URL, data=b"invalid")
    text = await req.json()
    assert req.status == HTTPStatus.BAD_REQUEST
    assert text["message"] == "Invalid JSON"

    req = await meraki_client.post(URL, data=b"{}")
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "No secret"

    data = {"version": "1.0", "secret": "secret"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid version"

    data = {"version": "2.0", "secret": "invalid"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid secret"

    data = {"version": "2.0", "secret": "secret", "type": "InvalidType"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid device type"

    data = {
        "version": "2.0",
        "secret": "secret",
        "type": "BluetoothDevicesSeen",
        "data": {"observations": []},
    }
    req = await meraki_client.post(URL, data=json.dumps(data))
    assert req.status == HTTPStatus.OK


async def test_data_will_be_saved(
    mock_device_tracker_conf: list[legacy.Device], hass: HomeAssistant, meraki_client
) -> None:
    """Test with valid data."""
    data = {
        "version": "2.0",
        "secret": "secret",
        "type": "DevicesSeen",
        "data": {
            "observations": [
                {
                    "location": {
                        "lat": "51.5355157",
                        "lng": "21.0699035",
                        "unc": "46.3610585",
                    },
                    "seenTime": "2016-09-12T16:23:13Z",
                    "ssid": "ssid",
                    "os": "HA",
                    "ipv6": "2607:f0d0:1002:51::4/64",
                    "clientMac": "00:26:ab:b8:a9:a4",
                    "seenEpoch": "147369739",
                    "rssi": "20",
                    "manufacturer": "Seiko Epson",
                },
                {
                    "location": {
                        "lat": "51.5355357",
                        "lng": "21.0699635",
                        "unc": "46.3610585",
                    },
                    "seenTime": "2016-09-12T16:21:13Z",
                    "ssid": "ssid",
                    "os": "HA",
                    "ipv4": "192.168.0.1",
                    "clientMac": "00:26:ab:b8:a9:a5",
                    "seenEpoch": "147369750",
                    "rssi": "20",
                    "manufacturer": "Seiko Epson",
                },
            ]
        },
    }
    req = await meraki_client.post(URL, data=json.dumps(data))
    assert req.status == HTTPStatus.OK
    await hass.async_block_till_done()
    state_name = hass.states.get("device_tracker.00_26_ab_b8_a9_a4").state
    assert state_name == "home"

    state_name = hass.states.get("device_tracker.00_26_ab_b8_a9_a5").state
    assert state_name == "home"


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_meraki_client")
async def test_trackers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the trackers of the clients."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("mock_meraki_client")
async def test_trackers_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test only clients known to another integration are tracked by default."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:01")},
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PHONE).state == STATE_HOME
    entry = entity_registry.async_get("device_tracker.nas")
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_leaves(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test clients are away when offline or no longer listed."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(PHONE).state == STATE_HOME

    clients = await async_load_json_array_fixture(hass, "clients.json", DOMAIN)
    clients[0]["status"] = "Offline"
    mock_meraki_client.networks.getNetworkClients.return_value = clients
    await _async_poll(hass, freezer)
    assert hass.states.get(PHONE).state == STATE_NOT_HOME

    # After an hour without connecting, the API stops listing a client.
    mock_meraki_client.networks.getNetworkClients.return_value = clients[1:]
    await _async_poll(hass, freezer)
    assert hass.states.get(PHONE).state == STATE_NOT_HOME


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_new_client(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test clients that connect later get a tracker."""
    await setup_integration(hass, mock_config_entry)
    clients = await async_load_json_array_fixture(hass, "clients.json", DOMAIN)
    new_client = {**clients[0], "mac": "aa:bb:cc:00:00:04", "description": "Tablet"}
    mock_meraki_client.networks.getNetworkClients.return_value = [*clients, new_client]
    await _async_poll(hass, freezer)
    assert hass.states.get("device_tracker.tablet").state == STATE_HOME


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_restore_unlisted_clients(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test trackers of clients the API no longer lists are away after a restart."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_meraki_client.networks.getNetworkClients.return_value = []
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PHONE).state == STATE_NOT_HOME


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_in_several_networks(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a client listed in two networks is home where it is online."""
    networks = await async_load_json_array_fixture(hass, "networks.json", DOMAIN)
    networks[1]["productTypes"] = ["wireless"]
    mock_meraki_client.organizations.getOrganizationNetworks.return_value = networks
    clients = await async_load_json_array_fixture(hass, "clients.json", DOMAIN)
    # Meraki documents lastSeen as a Unix timestamp; the fixture has the ISO
    # strings the API actually returns. 1792528200 is 2026-10-20 20:30 UTC.
    elsewhere = [
        {**client, "status": "Offline", "ip": "10.0.0.1", "lastSeen": 1792528200}
        for client in clients
    ]
    mock_meraki_client.networks.getNetworkClients.side_effect = [clients, elsewhere]
    await setup_integration(hass, mock_config_entry)

    phone = hass.states.get(PHONE)
    assert phone.state == STATE_HOME
    assert phone.attributes["ip"] == "192.168.1.20"
    # Offline in both, the more recent sighting (20:30 rather than 20:15) wins.
    laptop = hass.states.get("device_tracker.aa_bb_cc_00_00_03")
    assert laptop.attributes["ip"] == "10.0.0.1"


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_failed(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trackers become unavailable when the API fails."""
    await setup_integration(hass, mock_config_entry)
    mock_meraki_client.networks.getNetworkClients.side_effect = api_error(503)
    await _async_poll(hass, freezer)
    assert hass.states.get(PHONE).state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2026-10-20 21:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_meraki_client")
async def test_client_in_several_organizations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device in two organizations is tracked in each."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office",
        unique_id="654321",
        data={**mock_config_entry.data, CONF_ORGANIZATION_ID: "654321"},
    )
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, other_entry)

    first = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"{ORGANIZATION_ID}_aa:bb:cc:00:00:01"
    )
    second = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, "654321_aa:bb:cc:00:00:01"
    )
    assert first == PHONE
    assert second == f"{PHONE}_2"
    assert hass.states.get(second).state == STATE_HOME
