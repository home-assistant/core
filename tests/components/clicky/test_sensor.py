"""Tests for the Clicky sensor platform."""

from unittest.mock import AsyncMock, patch

from pyclicky import Report
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.components.clicky.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import _make_empty_report, _make_report


@pytest.fixture
def visitors_online_report() -> Report:
    """The report returned for visitors online."""
    return _make_report(12)


@pytest.fixture
def time_total_report() -> Report:
    """The report returned for total time spent."""
    return _make_report(345)


@pytest.fixture
async def client(
    visitors_online_report: Report, time_total_report: Report
) -> AsyncMock:
    """A ClickyClient mock returning fixed report values."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.return_value = visitors_online_report
    client.time_total.return_value = time_total_report

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
@pytest.mark.parametrize(
    ("visitors_online_report", "time_total_report", "visitors_state", "time_state"),
    [
        (_make_empty_report(), _make_report(345), "0", "345"),
        (_make_report(12), _make_empty_report(), "12", "0"),
    ],
    ids=["visitors_online_empty", "time_total_empty"],
)
async def test_sensor_empty_report(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    visitors_state: str,
    time_state: str,
) -> None:
    """Test that a report without a value is published as zero, not unknown."""

    visitors_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "12345_visitorsOnline"
    )
    time_total_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "12345_timeTotal"
    )

    assert hass.states.get(visitors_id).state == visitors_state
    assert hass.states.get(time_total_id).state == time_state


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
