"""The sensor tests for the Ruckus platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioruckus.const import ERROR_CONNECT_EOF, ERROR_LOGIN_INCORRECT
from aioruckus.exceptions import AuthenticationError

from homeassistant.components.ruckus_unleashed.const import (
    API_CLIENT_MAC,
    CONF_MAC_FILTER,
    DOMAIN,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import utcnow

from . import (
    DEFAULT_UNIQUEID,
    TEST_CLIENT,
    TEST_CLIENT_2,
    TEST_CLIENT_2_ENTITY_ID,
    TEST_CLIENT_ENTITY_ID,
    RuckusAjaxApiPatchContext,
    init_integration,
    mock_config_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test restoring existing device_tracker entities if not detected on startup."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        DEFAULT_UNIQUEID,
        suggested_object_id="ruckus_test_device",
        config_entry=entry,
    )

    with RuckusAjaxApiPatchContext(active_clients={}):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = hass.states.get(TEST_CLIENT_ENTITY_ID)
    assert device is not None
    assert device.state == STATE_NOT_HOME


async def test_mac_filter_tracks_only_allowed(hass: HomeAssistant) -> None:
    """Test that only allowed clients are tracked when mac_filter is set."""
    entry = mock_config_entry(options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]})
    entry.add_to_hass(hass)
    # Create devices from another integration so device tracker entities get enabled
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    for client in (TEST_CLIENT, TEST_CLIENT_2):
        device_registry.async_get_or_create(
            name=f"Device {client[API_CLIENT_MAC]}",
            config_entry_id=other_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, client[API_CLIENT_MAC])},
        )

    with RuckusAjaxApiPatchContext(active_clients=[TEST_CLIENT, TEST_CLIENT_2]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Allowed client should be tracked
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None
    assert hass.states.get(TEST_CLIENT_ENTITY_ID).state == STATE_HOME

    # Non-allowed client should not exist
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is None


async def test_empty_mac_filter_tracks_all(hass: HomeAssistant) -> None:
    """Test that all clients are tracked when mac_filter is empty."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    # Create devices from another integration so device tracker entities get enabled
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    for client in (TEST_CLIENT, TEST_CLIENT_2):
        device_registry.async_get_or_create(
            name=f"Device {client[API_CLIENT_MAC]}",
            config_entry_id=other_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, client[API_CLIENT_MAC])},
        )

    with RuckusAjaxApiPatchContext(active_clients=[TEST_CLIENT, TEST_CLIENT_2]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Both clients should be tracked
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is not None


async def test_mac_filter_restore_respects_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that restore_entities respects mac_filter."""
    entry = mock_config_entry(options={CONF_MAC_FILTER: [TEST_CLIENT[API_CLIENT_MAC]]})
    entry.add_to_hass(hass)

    # Pre-create entities for both clients in the registry
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

    # Only allowed client should be restored
    assert hass.states.get(TEST_CLIENT_ENTITY_ID) is not None
    assert hass.states.get(TEST_CLIENT_ENTITY_ID).state == STATE_NOT_HOME

    # Non-allowed client should not be restored
    assert hass.states.get(TEST_CLIENT_2_ENTITY_ID) is None
