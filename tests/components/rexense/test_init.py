"""Test gateway setup, resource ownership and unloading."""

from unittest.mock import MagicMock, patch

from aiorexense import (
    RexenseAuthenticationError,
    RexenseConnectionError,
    RexenseError,
    UnsupportedTaxonomyError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rexense.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import GATEWAY_ID, MAC

ENTITY_ID = "switch.tl0001_switch_1"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Register stable devices and release both connection and subscription."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.gateway is mock_gateway
    mock_gateway.async_start.assert_awaited_once()
    assert hass.states.get(ENTITY_ID) == snapshot(name="state")
    assert entity_registry.async_get(ENTITY_ID) == snapshot(name="entity")
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, GATEWAY_ID), mock_config_entry.entry_id
    ) == snapshot(name="gateway")
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{GATEWAY_ID}_{MAC}"), mock_config_entry.entry_id
    ) == snapshot(name="switch")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_gateway.async_stop.assert_awaited_once()
    mock_gateway.subscribe.return_value.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        pytest.param(
            RexenseAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            id="authentication",
        ),
        pytest.param(
            UnsupportedTaxonomyError, ConfigEntryState.SETUP_ERROR, id="taxonomy"
        ),
        pytest.param(
            RexenseConnectionError, ConfigEntryState.SETUP_RETRY, id="connection"
        ),
        pytest.param(RexenseError, ConfigEntryState.SETUP_RETRY, id="protocol"),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Translate library failures before creating any entities."""
    mock_gateway.async_start.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is state
    assert not hass.states.async_entity_ids("switch")
    mock_gateway.subscribe.assert_not_called()


async def test_platform_setup_failure_closes_gateway(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Release the live SDK connection if platform forwarding fails."""
    mock_config_entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_gateway.async_stop.assert_awaited_once()


async def test_home_assistant_stop(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Close the SDK connection when Home Assistant shuts down."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_gateway.async_stop.assert_awaited_once()


async def test_reload_retains_entity_identity(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Reload keeps the same registry entry and recreates its subscription."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(ENTITY_ID).id == entity.id
    assert mock_gateway.async_start.await_count == 2
    mock_gateway.async_stop.assert_awaited_once()
    mock_gateway.subscribe.return_value.assert_called_once()
    assert mock_gateway.subscribe.call_count == 2
