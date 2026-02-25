"""Tests for ZoneMinder binary sensor entity states (public API)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST, MOCK_HOST_2

from tests.common import async_fire_time_changed

# The entity_id uses the hostname with dots replaced by underscores
ENTITY_ID = f"binary_sensor.{MOCK_HOST.replace('.', '_')}"
ENTITY_ID_2 = f"binary_sensor.{MOCK_HOST_2.replace('.', '_')}"


async def _setup_and_update(
    hass: HomeAssistant,
    config: dict,
    mock_zoneminder_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Set up ZM component and trigger first entity update."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Trigger the first update poll while mock is still active
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_binary_sensor_created_per_server(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one binary sensor entity is created per ZM server."""
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None


async def test_binary_sensor_name_from_hostname(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor entity name matches hostname."""
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == MOCK_HOST


async def test_binary_sensor_device_class_connectivity(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor has connectivity device class."""
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


async def test_binary_sensor_state_on_when_available(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor state is ON when server is available."""
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=True)
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_state_off_when_unavailable(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor state is OFF when server is unavailable."""
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=False)
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_multi_server_creates_multiple_binary_sensors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    multi_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test multi-server config creates multiple binary sensor entities."""
    assert await async_setup_component(hass, DOMAIN, multi_server_config)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get(ENTITY_ID_2) is not None


async def test_binary_sensor_state_updates_on_poll(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor state updates when polled."""
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=True)
    await _setup_and_update(hass, single_server_config, mock_zoneminder_client, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Change availability and trigger another update
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=False)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
