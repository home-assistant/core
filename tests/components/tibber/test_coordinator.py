"""Tests for the Tibber coordinators."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import create_tibber_home

from tests.common import MockConfigEntry, async_fire_time_changed


def _prices_for_days(*days: str) -> dict[str, float]:
    """Return price data keyed by ISO timestamps for the given days."""
    return {f"{day}T12:00:00+00:00": 1.0 for day in days}


async def _async_setup_price_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    home: MagicMock,
) -> str:
    """Set up the Tibber config entry and return the price sensor entity id."""
    tibber_mock.get_homes.return_value = [home]
    config_entry.data["token"]["expires_at"] = dt_util.utcnow().timestamp() + 86400

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, home.home_id)
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None
    return entity_id


async def _async_fire_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    delta: timedelta,
) -> None:
    """Move time forward and fire scheduled coordinator updates."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_price_fetch_refreshes_when_today_prices_are_missing(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test price fetching when cached prices do not include today."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-04-26 00:10:00+00:00")
    home = create_tibber_home(price_total=_prices_for_days("2026-04-25"))

    async def update_info_and_price_info() -> None:
        home.price_total = _prices_for_days("2026-04-26")

    home.update_info_and_price_info.side_effect = update_info_and_price_info

    await _async_setup_price_sensor(
        hass, config_entry, tibber_mock, entity_registry, home
    )

    assert home.update_info_and_price_info.await_count == 1

    await _async_fire_coordinator_update(hass, freezer, timedelta(hours=3))

    assert home.update_info_and_price_info.await_count == 1


async def test_price_fetch_waits_until_tomorrow_price_polling_window(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test price fetching waits until the tomorrow-price polling window."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-04-26 13:00:00+00:00")
    home = create_tibber_home(price_total=_prices_for_days("2026-04-26"))

    async def update_info_and_price_info() -> None:
        home.price_total = _prices_for_days("2026-04-26", "2026-04-27")

    home.update_info_and_price_info.side_effect = update_info_and_price_info

    await _async_setup_price_sensor(
        hass, config_entry, tibber_mock, entity_registry, home
    )

    assert home.update_info_and_price_info.await_count == 0

    await _async_fire_coordinator_update(hass, freezer, timedelta(minutes=10))

    assert home.update_info_and_price_info.await_count == 0

    await _async_fire_coordinator_update(hass, freezer, timedelta(hours=9, minutes=50))

    assert home.update_info_and_price_info.await_count == 1

    await _async_fire_coordinator_update(hass, freezer, timedelta(hours=10))

    assert home.update_info_and_price_info.await_count == 1


async def test_price_fetch_skips_update_when_tomorrow_prices_exist(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test price fetching skips homes that already have tomorrow prices."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-04-26 23:00:00+00:00")
    home = create_tibber_home(price_total=_prices_for_days("2026-04-26", "2026-04-27"))

    await _async_setup_price_sensor(
        hass, config_entry, tibber_mock, entity_registry, home
    )

    await _async_fire_coordinator_update(hass, freezer, timedelta(minutes=10))

    assert home.update_info_and_price_info.await_count == 0


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]
