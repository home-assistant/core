"""Test the ENGIE Belgium binary sensor platform."""

from datetime import date, datetime
import logging
from unittest.mock import MagicMock

from aioengiebelgium import (
    EngieBeCommunicationError,
    EpexGranularity,
    EpexPayload,
    EpexSlot,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.engie_be.const import DOMAIN, EPEX_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BAN,
    BRUSSELS_TIME_ZONE,
    build_epex_payload,
    build_epex_payload_with_partial_tomorrow,
    build_epex_payload_without_tomorrow,
    setup_dynamic_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the binary sensor is off while tomorrow's prices are unpublished."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.engie_be")
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
    assert "Fetching EPEX prices for 2026-10-04 failed" in caplog.text


async def test_tomorrow_prices_partial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    frozen_afternoon: None,
) -> None:
    """Test the binary sensor stays off until tomorrow is fully covered."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_partial_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    client = mock_engie_client.return_value
    call_count = client.async_get_epex_prices.call_count
    client.async_get_epex_prices.side_effect = build_epex_payload
    freezer.tick(EPEX_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_get_epex_prices.call_count == call_count + 2

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


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


async def test_tomorrow_prices_with_stretched_slot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test the binary sensor stays off when a slot of tomorrow has the wrong length."""

    def _stretched_tomorrow(
        start: datetime,
        end: datetime,
        granularity: EpexGranularity = EpexGranularity.HOURLY,
    ) -> EpexPayload:
        """Merge the last two slots of tomorrow into one double length slot."""
        payload = build_epex_payload(start, end, granularity)
        if start.astimezone(BRUSSELS_TIME_ZONE).date() != date(2026, 10, 4):
            return payload
        *head, before_last, last = payload.slots
        merged = EpexSlot(
            start=before_last.start,
            end=last.end,
            value_eur_per_kwh=before_last.value_eur_per_kwh,
        )
        return EpexPayload(slots=(*head, merged), slot_duration=payload.slot_duration)

    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        _stretched_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
