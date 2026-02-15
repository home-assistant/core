"""Tests for ZoneMinder binary sensor entity states (public API)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MOCK_HOST, MOCK_HOST_2, create_mock_zm_client

from tests.common import async_fire_time_changed

# The entity_id uses the hostname with dots replaced by underscores
ENTITY_ID = f"binary_sensor.{MOCK_HOST.replace('.', '_')}"
ENTITY_ID_2 = f"binary_sensor.{MOCK_HOST_2.replace('.', '_')}"


async def _setup_and_update(hass: HomeAssistant, config, client):
    """Set up ZM component and trigger first entity update."""
    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Trigger the first update poll while mock is still active
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)


async def test_binary_sensor_created_per_server(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test one binary sensor entity is created per ZM server."""
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None


async def test_binary_sensor_name_from_hostname(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test binary sensor entity name matches hostname."""
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == MOCK_HOST


async def test_binary_sensor_device_class_connectivity(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test binary sensor has connectivity device class."""
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


async def test_binary_sensor_state_on_when_available(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test binary sensor state is ON when server is available."""
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_state_off_when_unavailable(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test binary sensor state is OFF when server is unavailable."""
    client = create_mock_zm_client(is_available=False)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_multi_server_creates_multiple_binary_sensors(
    hass: HomeAssistant, multi_server_config
) -> None:
    """Test multi-server config creates multiple binary sensor entities."""
    client = create_mock_zm_client(is_available=True)

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, multi_server_config)
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get(ENTITY_ID_2) is not None


async def test_binary_sensor_state_updates_on_poll(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test binary sensor state updates when polled."""
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Change availability and trigger another update
    type(client).is_available = PropertyMock(return_value=False)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=120), fire_all=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.xfail(reason="BUG-05: No unique_id on any entity")
async def test_unique_id_set(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, single_server_config
) -> None:
    """Binary sensor should have unique_id for UI customization.

    No entity in the integration sets unique_id. This means entities cannot
    be customized via the HA UI and are fragile to name changes.
    """
    client = create_mock_zm_client(is_available=True)
    await _setup_and_update(hass, single_server_config, client)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id is not None
