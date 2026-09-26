"""Tests for the Clicky sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.components.clicky.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import _make_report

from tests.common import MockConfigEntry


@pytest.fixture
async def client() -> AsyncMock:
    """A ClickyClient mock returning fixed report values."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.return_value = _make_report(12)
    client.time_total.return_value = _make_report(345)

    return client


@pytest.fixture
async def setup_entry(hass: HomeAssistant, client: AsyncMock) -> MockConfigEntry:
    """Set up a Clicky config entry backed by the mocked client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: "12345",
            CONF_SITEKEY: "abcdef",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.clicky.ClickyClient",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Test that async_setup_entry creates the expected sensors."""

    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.platform == DOMAIN
    ]

    assert len(entities) == len(SENSOR_TYPES)

    unique_ids = {entity.unique_id for entity in entities}
    assert unique_ids == {"12345_visitorsOnline", "12345_timeTotal"}


@pytest.mark.asyncio
async def test_sensor_native_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Test native_value returns coordinator data via the state machine."""

    visitors_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "12345_visitorsOnline"
    )
    time_total_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "12345_timeTotal"
    )

    assert hass.states.get(visitors_id).state == "12"
    assert hass.states.get(time_total_id).state == "345"


@pytest.mark.asyncio
async def test_sensor_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Test static sensor attributes via the entity registry."""

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "12345_visitorsOnline"
    )
    entry = entity_registry.entities[entity_id]

    assert entry.unique_id == "12345_visitorsOnline"
    assert entry.original_name == "Visitors Online"
