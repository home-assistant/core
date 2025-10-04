"""Tests for Google Maps Travel Time init."""

import pytest

from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_TIME,
    CONF_TIME_TYPE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_OPTIONS, MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("v1", "v2"),
    [
        ("08:00", "08:00"),
        ("08:00:00", "08:00:00"),
        ("1742144400", "17:00"),
        ("now", None),
        (None, None),
    ],
)
@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_migrate_entry_v1_v2(
    hass: HomeAssistant,
    v1: str,
    v2: str | None,
) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            **DEFAULT_OPTIONS,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: v1,
        },
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.options[CONF_TIME] == v2


@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_migrate_entry_v1_v2_invalid_time(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            **DEFAULT_OPTIONS,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "invalid",
        },
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.options[CONF_TIME] is None
    assert "Invalid time format found while migrating" in caplog.text


@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_migrate_entry_v2_v3(
    hass: HomeAssistant,
) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=MOCK_CONFIG,
        options={
            **DEFAULT_OPTIONS,
        },
    )
    mock_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    old_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        mock_entry.entry_id,
        suggested_object_id="google_travel_time",
        config_entry=mock_entry,
    )
    assert old_entity.entity_id == "sensor.google_travel_time"

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry.state is ConfigEntryState.LOADED

    old_unique_id = mock_entry.entry_id
    new_unique_id = f"{old_unique_id}_duration"

    new_entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
    assert new_entity_id == f"{old_entity.entity_id}_duration"
