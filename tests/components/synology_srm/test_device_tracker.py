"""Test Synology SRM trackers and the end-user migration workflow."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import ConnectionError
from synology_srm.http import SynologyApiError

from homeassistant.components.synology_srm.const import CONF_TRACKED_DEVICES, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import CLIENT, CONFIG, MAC


async def test_trackers(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test disabled defaults, enabling, updates, discovery, and unloading."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
    entry = entity_registry.async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.original_name is None
    assert hass.states.get(entity_id) is None
    device = device_registry.async_get(entry.device_id)
    assert device.name == "Phone"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    mock_client.core.get_network_nsm_device.return_value = [
        {**CLIENT, "hostname": "Renamed"}
    ]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert device_registry.async_get(device.id).name == "Renamed"

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_HOME
    assert hass.states.get(entity_id).attributes["signal_strength"] == -50
    assert hass.states.get(entity_id).attributes["ip"] == CLIENT["ip_addr"]

    mock_client.core.get_network_nsm_device.return_value = []
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_NOT_HOME
    mock_client.core.get_network_nsm_device.side_effect = ConnectionError()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    mock_client.core.get_network_nsm_device.side_effect = None
    mock_client.core.get_network_nsm_device.return_value = [
        CLIENT,
        {**CLIENT, "mac": "11:22:33:44:55:66", "hostname": "New"},
    ]
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_HOME
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 2
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_offline_at_startup(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An existing enabled tracker remains available even if absent from the API."""
    mock_client.core.get_network_nsm_device.return_value = []
    mock_config_entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        MAC,
        config_entry=mock_config_entry,
        suggested_object_id="old_phone",
        disabled_by=None,
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == STATE_NOT_HOME


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ConnectionError(), ConfigEntryState.SETUP_RETRY, id="connection"),
        pytest.param(
            SynologyApiError(400, "Invalid login"),
            ConfigEntryState.SETUP_ERROR,
            id="auth",
        ),
        pytest.param(
            SynologyApiError(500, "API failure"), ConfigEntryState.SETUP_RETRY, id="api"
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected: ConfigEntryState,
) -> None:
    """Test startup failure handling."""
    mock_client.core.get_network_nsm_device.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is expected


async def test_preserve_person_assignment(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Restore a person assignment manually after the legacy ID has been released."""
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "test_user",
                    "name": "Test User",
                    "device_trackers": ["device_tracker.old_phone"],
                }
            ]
        },
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
    assert hass.states.get("device_tracker.old_phone") is None
    entity_registry.async_update_entity(
        entity_id, disabled_by=None, new_entity_id="device_tracker.old_phone"
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    person = hass.states.get("person.test_user")
    assert person.state == STATE_HOME
    assert person.attributes["device_trackers"] == ["device_tracker.old_phone"]
    assert person.attributes["source"] == "device_tracker.old_phone"
    mock_client.core.get_network_nsm_device.return_value = []
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("person.test_user").state == STATE_NOT_HOME


async def test_selected_devices(
    hass: HomeAssistant,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Only explicitly selected devices start enabled, including after a reload."""
    other_mac = "11:22:33:44:55:66"
    mock_client.core.get_network_nsm_device.return_value = [
        CLIENT,
        {**CLIENT, "mac": other_mac, "hostname": "Other"},
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
    )
    await hass.async_block_till_done()
    config_entry = result["result"]
    selected_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
    other_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, other_mac)
    selected_device = device_registry.async_get(
        entity_registry.async_get(selected_id).device_id
    )
    other_device = device_registry.async_get(
        entity_registry.async_get(other_id).device_id
    )
    assert not selected_device.disabled
    assert other_device.disabled
    assert entity_registry.async_get(selected_id).disabled_by is None
    assert hass.states.get(selected_id).state == STATE_HOME
    assert (
        entity_registry.async_get(other_id).disabled_by
        is er.RegistryEntryDisabler.DEVICE
    )
    assert hass.states.get(other_id) is None
    device_registry.async_update_device(other_device.id, disabled_by=None)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(other_id).disabled_by is None
    assert hass.states.get(other_id).state == STATE_HOME
    entity_registry.async_update_entity(
        selected_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get(selected_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )
    assert entity_registry.async_get(other_id).disabled_by is None

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(selected_id).disabled_by is None
    assert hass.states.get(selected_id).state == STATE_HOME
    assert not device_registry.async_get(
        entity_registry.async_get(selected_id).device_id
    ).disabled
    assert device_registry.async_get(
        entity_registry.async_get(other_id).device_id
    ).disabled
    assert (
        entity_registry.async_get(other_id).disabled_by
        is er.RegistryEntryDisabler.DEVICE
    )


async def test_shared_mac_keeps_router_ownership(
    hass: HomeAssistant,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second router cannot claim or change another router's tracker."""
    first = MockConfigEntry(domain=DOMAIN, data={**CONFIG, CONF_TRACKED_DEVICES: [MAC]})
    first.add_to_hass(hass)
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
    original = entity_registry.async_get(entity_id)
    other_mac = "11:22:33:44:55:66"
    mock_client.core.get_network_nsm_device.return_value = [
        CLIENT,
        {**CLIENT, "mac": other_mac, "hostname": "Other"},
    ]
    second = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG, "host": "192.168.2.1", CONF_TRACKED_DEVICES: [other_mac]},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) == original
    assert not device_registry.async_get(original.device_id).disabled
    assert hass.states.get(entity_id).state == STATE_HOME
    other_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, other_mac)
    assert entity_registry.async_get(other_id).config_entry_id == second.entry_id
    assert hass.states.get(other_id).state == STATE_HOME

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(second.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) == original
    assert entity_registry.async_get(other_id).config_entry_id == second.entry_id
    assert not device_registry.async_get(original.device_id).disabled
    assert hass.states.get(entity_id).state == STATE_HOME
    assert hass.states.get(other_id).state == STATE_HOME
