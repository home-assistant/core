"""The test for the sensibo select platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysensibo.model import PureAQI, SensiboData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SENSOR]],
)
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo sensor."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    monkeypatch.setattr(get_data[0].parsed["AAZZAAZZ"], "pm25_pure", PureAQI(2))

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.kitchen_pure_aqi")
    assert state.state == "moderate"
