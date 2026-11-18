"""Tests for the Ablago binary sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from ablago import AblagoConnectionError, Gesundheit
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    snapshot_platform,
)

from homeassistant.components.ablago.const import UPDATE_INTERVAL_COUNTERS
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

NEW_MAIL_WAITING = "binary_sensor.ablago_example_org_new_mail_waiting"
CONNECTIVITY = "binary_sensor.ablago_example_org_connectivity"


async def test_binary_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ablago_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensors."""
    with patch("homeassistant.components.ablago.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(UPDATE_INTERVAL_COUNTERS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_new_mail_waiting(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the binary sensor follows the new mail counter."""
    assert hass.states.get(NEW_MAIL_WAITING).state == STATE_ON
    counters = mock_ablago_client.zaehler.return_value
    mock_ablago_client.zaehler.return_value = replace(counters, neue_post=0, stand=43)
    await _tick(hass, freezer)
    assert hass.states.get(NEW_MAIL_WAITING).state == STATE_OFF


@pytest.mark.parametrize(
    ("health", "side_effect"),
    [
        pytest.param(None, AblagoConnectionError("gone"), id="unreachable"),
        pytest.param(
            Gesundheit(ok=False, zustand="datenbank", seit=None), None, id="not_ready"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_disconnected(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    health: Gesundheit | None,
    side_effect: Exception | None,
) -> None:
    """Test connectivity turns off instead of becoming unavailable."""
    assert hass.states.get(CONNECTIVITY).state == STATE_ON
    mock_ablago_client.gesundheit.return_value = health
    mock_ablago_client.gesundheit.side_effect = side_effect
    await _tick(hass, freezer)
    assert hass.states.get(CONNECTIVITY).state == STATE_OFF
