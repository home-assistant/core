"""Test integration setup, polling and recovery."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from xiaomi_weather import XiaomiWeatherError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "weather.beijing"


async def test_setup_unload(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup and unloading."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    client.get_weather.assert_awaited_once()
    entities = entity_registry.entities
    assert (
        len([e for e in entities.values() if e.config_entry_id == entry.entry_id]) == 1
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("failure", "unit"),
    [
        pytest.param(XiaomiWeatherError, "℃", id="request-error"),
        pytest.param(None, "F", id="unsupported-temperature"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    failure: type[XiaomiWeatherError] | None,
    unit: str,
) -> None:
    """Retry setup when required current weather is unusable."""
    client.get_weather.side_effect = failure
    data = client.get_weather.return_value
    client.get_weather.return_value = replace(
        data,
        current=replace(
            data.current, temperature=replace(data.current.temperature, unit=unit)
        ),
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("failure", "unit"),
    [
        pytest.param(XiaomiWeatherError, "℃", id="request-error"),
        pytest.param(None, "F", id="unsupported-temperature"),
    ],
)
@pytest.mark.usefixtures("entity_registry")
async def test_update_and_recovery(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    failure: type[XiaomiWeatherError] | None,
    unit: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update and recovery."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.get_weather.side_effect = failure
    data = client.get_weather.return_value
    client.get_weather.return_value = replace(
        data,
        current=replace(
            data.current, temperature=replace(data.current.temperature, unit=unit)
        ),
    )
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None and state.state == "unavailable"
    client.get_weather.side_effect = None
    client.get_weather.return_value = replace(
        client.get_weather.return_value,
        current=replace(
            client.get_weather.return_value.current,
            temperature=replace(
                client.get_weather.return_value.current.temperature, value=22, unit="℃"
            ),
        ),
    )
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None and state.attributes["temperature"] == 22


async def test_poll_and_unload(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One scheduled request serves all entities; unloading cancels the next one."""

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.get_weather.assert_awaited_once()
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.get_weather.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.get_weather.await_count == 2


async def test_independent_locations(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Unloading one location leaves the other location operational."""
    other = MockConfigEntry(
        domain="xiaomi_weather",
        title="Shanghai",
        unique_id="101020100",
        data={
            "name": "Shanghai",
            "city_id": "101020100",
            "latitude": 31.2,
            "longitude": 121.5,
        },
    )
    for config_entry in (entry, other):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert client.get_weather.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    state = hass.states.get("weather.shanghai")
    assert state is not None and state.state == "partlycloudy"
