"""The sensor tests for the Ruckus Unleashed platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioruckus.const import ERROR_CONNECT_EOF, ERROR_LOGIN_INCORRECT
from aioruckus.exceptions import AuthenticationError

from homeassistant.components.ruckus_unleashed import DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import utcnow

from . import (
    DEFAULT_UNIQUEID,
    TEST_CLIENT_ENTITY_ID,
    RuckusAjaxApiPatchContext,
    init_integration,
    mock_config_entry,
)

from tests.common import async_fire_time_changed


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


async def test_restoring_clients(hass: HomeAssistant) -> None:
    """Test restoring existing device_tracker entities if not detected on startup."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    registry.async_get_or_create(
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
