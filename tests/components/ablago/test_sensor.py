"""Tests for the Ablago sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from ablago import AblagoAuthError, AblagoConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    snapshot_platform,
)

from homeassistant.components.ablago.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

NEW_MAIL = "sensor.ablago_example_org_new_mail"


async def test_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ablago_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_update(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new counters show up after the next poll."""
    assert hass.states.get(NEW_MAIL).state == "3"
    counters = mock_ablago_client.zaehler.return_value
    mock_ablago_client.zaehler.return_value = replace(counters, neue_post=0, stand=43)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEW_MAIL).state == "0"


@pytest.mark.usefixtures("init_integration")
async def test_unreachable(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the counters become unavailable while Ablago is unreachable."""
    mock_ablago_client.zaehler.side_effect = AblagoConnectionError("gone")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEW_MAIL).state == STATE_UNAVAILABLE

    mock_ablago_client.zaehler.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEW_MAIL).state == "3"


@pytest.mark.usefixtures("init_integration")
async def test_key_revoked(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a key revoked while running makes the entities unavailable and stops polling."""
    mock_ablago_client.zaehler.side_effect = AblagoAuthError("401", status=401)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEW_MAIL).state == STATE_UNAVAILABLE
    calls = mock_ablago_client.zaehler.call_count

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_ablago_client.zaehler.call_count == calls
