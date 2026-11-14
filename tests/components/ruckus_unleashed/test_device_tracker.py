"""The sensor tests for the Ruckus platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioruckus.const import ERROR_CONNECT_EOF, ERROR_LOGIN_INCORRECT
from aioruckus.exceptions import AuthenticationError
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.ruckus_unleashed.const import (
    API_CLIENT_HOSTNAME,
    API_CLIENT_MAC,
    CONF_MAC_FILTER,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import utcnow

from . import (
    TEST_CLIENT,
    TEST_CLIENT_2,
    TEST_CLIENT_2_ENTITY_ID,
    TEST_CLIENT_ENTITY_ID,
    RuckusAjaxApiPatchContext,
    init_integration,
    mock_config_entry,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_connected(hass: HomeAssistant) -> None:
    """Test client connected."""
    await init_integration(hass)

    future = utcnow() + timedelta(minutes=60)
    with RuckusAjaxApiPatchContext():
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        await async_update_entity(hass, TEST_CLIENT_ENTITY_ID)

    test_client = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert test_client.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_disconnected(hass: HomeAssistant) -> None:
    """Test client disconnected."""
    await init_integration(hass)

    future = utcnow() + timedelta(minutes=60)
    with RuckusAjaxApiPatchContext(active_clients={}):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        await async_update_entity(hass, TEST_CLIENT_ENTITY_ID)
        test_client = hass.states.get(TEST_CLIENT_ENTITY_ID)
        assert test_client.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_clients_update_failed(hass: HomeAssistant) -> None:
    """Test failed update."""
    await init_integration(hass)

    future = utcnow() + timedelta(minutes=60)
    with RuckusAjaxApiPatchContext(
        active_clients=AsyncMock(side_effect=ConnectionError(ERROR_CONNECT_EOF))
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        await async_update_entity(hass, TEST_CLIENT_ENTITY_ID)
        test_client = hass.states.get(TEST_CLIENT_ENTITY_ID)
        assert test_client.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_clients_update_auth_failed(hass: HomeAssistant) -> None:
    """Test failed update with bad auth."""
    await init_integration(hass)

    future = utcnow() + timedelta(minutes=60)
    with RuckusAjaxApiPatchContext(
        active_clients=AsyncMock(side_effect=AuthenticationError(ERROR_LOGIN_INCORRECT))
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        await async_update_entity(hass, TEST_CLIENT_ENTITY_ID)
        test_client = hass.states.get(TEST_CLIENT_ENTITY_ID)
        assert test_client.state == STATE_UNAVAILABLE


async def test_restoring_clients(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test restoring existing device_tracker entities if not detected on startup."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        TEST_CLIENT[API_CLIENT_MAC],
        suggested_object_id="ruckus_test_device",
        config_entry=entry,
    )

    with RuckusAjaxApiPatchContext(active_clients={}):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert device is not None
    assert device.state == STATE_NOT_HOME
    entity_entry = entity_registry.async_get(TEST_CLIENT_ENTITY_ID)
    assert entity_entry is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.name == TEST_CLIENT[API_CLIENT_MAC]
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TEST_CLIENT[API_CLIENT_MAC]))
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_mac_filter_tracks_only_allowed(hass: HomeAssistant) -> None:
    """Test that only allowed MACs are tracked when filter is set."""
    entry = mock_config_entry(options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]})
    entry.add_to_hass(hass)

    with RuckusAjaxApiPatchContext(
        active_clients=[TEST_CLIENT, TEST_CLIENT_2],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # TEST_CLIENT should be tracked
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None

    # TEST_CLIENT_2 should NOT be tracked (not in filter)
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_empty_mac_filter_tracks_all(hass: HomeAssistant) -> None:
    """Test that an empty filter tracks all clients."""
    entry = mock_config_entry(options={CONF_MAC_FILTER: []})
    entry.add_to_hass(hass)

    with RuckusAjaxApiPatchContext(
        active_clients=[TEST_CLIENT, TEST_CLIENT_2],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Both clients should be tracked
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is not None


async def test_mac_filter_restore_respects_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that restore_entities respects the MAC filter."""
    entry = mock_config_entry(options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]})
    entry.add_to_hass(hass)

    # Pre-create entities for both clients (simulating previously tracked)
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        TEST_CLIENT[API_CLIENT_MAC],
        suggested_object_id="ruckus_test_device",
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        TEST_CLIENT_2[API_CLIENT_MAC],
        suggested_object_id="ruckus_test_device_2",
        config_entry=entry,
    )

    # Start with no active clients so restore_entities runs
    with RuckusAjaxApiPatchContext(active_clients=[]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # TEST_CLIENT should be restored (in filter)
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None

    # TEST_CLIENT_2 should NOT be restored (not in filter)
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the client hostname names the tracker's device and the tracker."""
    await init_integration(hass)

    entity_entry = entity_registry.async_get(TEST_CLIENT_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == TEST_CLIENT[API_CLIENT_HOSTNAME]
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TEST_CLIENT[API_CLIENT_MAC]))
    }
    assert (
        hass.states.get(TEST_CLIENT_ENTITY_ID).attributes[ATTR_FRIENDLY_NAME]
        == TEST_CLIENT[API_CLIENT_HOSTNAME]
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_without_hostname(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a client without a hostname names its device by the MAC address."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with RuckusAjaxApiPatchContext(
        active_clients=[{**TEST_CLIENT, API_CLIENT_HOSTNAME: ""}]
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("device_tracker.aa_bb_cc_dd_ee_ff")
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == TEST_CLIENT[API_CLIENT_MAC]
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(TEST_CLIENT[API_CLIENT_MAC]))
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_hostname_change_renames_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a hostname change of a connected client renames its device."""
    await init_integration(hass)
    entity_entry = entity_registry.async_get(TEST_CLIENT_ENTITY_ID)
    assert entity_entry is not None

    with RuckusAjaxApiPatchContext(
        active_clients=[{**TEST_CLIENT, API_CLIENT_HOSTNAME: "New name"}]
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(minutes=60))
        await hass.async_block_till_done()

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "New name"
    assert (
        hass.states.get(TEST_CLIENT_ENTITY_ID).attributes[ATTR_FRIENDLY_NAME]
        == "New name"
    )

    # A disconnected client reports no hostname, so its device keeps its name
    with RuckusAjaxApiPatchContext(active_clients=[]):
        async_fire_time_changed(hass, utcnow() + timedelta(minutes=120))
        await hass.async_block_till_done()

    state = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "New name"
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "New name"


@pytest.mark.parametrize(
    ("device_name", "original_name", "expected_name"),
    [
        pytest.param("Restored name", None, "Restored name", id="named_device"),
        # The device of a tracker from before the client name moved to the
        # device was named by the MAC address
        pytest.param(
            TEST_CLIENT[API_CLIENT_MAC], "Old name", "Old name", id="old_entry"
        ),
    ],
)
async def test_restoring_client_name_with_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_name: str,
    original_name: str | None,
    expected_name: str,
) -> None:
    """Test the name of a client not detected on startup."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, TEST_CLIENT[API_CLIENT_MAC])},
        name=device_name,
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        TEST_CLIENT[API_CLIENT_MAC],
        suggested_object_id="ruckus_test_device",
        config_entry=entry,
        device_id=device.id,
        original_name=original_name,
    )

    with RuckusAjaxApiPatchContext(active_clients=[]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == expected_name
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == expected_name


async def test_restoring_client_name_without_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a restored client without a device names it by its original name."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        TEST_CLIENT[API_CLIENT_MAC],
        suggested_object_id="ruckus_test_device",
        config_entry=entry,
        original_name="Old name",
    )

    with RuckusAjaxApiPatchContext(active_clients=[]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Old name"
    entity_entry = entity_registry.async_get(TEST_CLIENT_ENTITY_ID)
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "Old name"
