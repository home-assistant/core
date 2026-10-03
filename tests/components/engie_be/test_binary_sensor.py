"""Test the ENGIE Belgium binary sensor platform."""

from unittest.mock import MagicMock

from aioengiebelgium import EngieBeCommunicationError
import pytest

from homeassistant.components.engie_be.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import BAN, build_epex_payload_without_tomorrow, setup_dynamic_entry

from tests.common import MockConfigEntry


async def test_tomorrow_prices_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test the binary sensor is on when tomorrow's prices are published."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.name.endswith("EPEX tomorrow prices available")

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.entity_category is er.EntityCategory.DIAGNOSTIC


async def test_tomorrow_prices_not_published(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test the binary sensor is off while tomorrow's prices are unpublished."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_without_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    current_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_hour"
    )
    assert current_entity_id is not None
    current_state = hass.states.get(current_entity_id)
    assert current_state is not None
    assert float(current_state.state) == pytest.approx(0.15)


async def test_tomorrow_prices_unavailable_when_fetch_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test the binary sensor is unavailable when the EPEX fetch fails at setup."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
