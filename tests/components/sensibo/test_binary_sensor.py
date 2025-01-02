"""The test for the sensibo binary sensor platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysensibo import SensiboData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.BINARY_SENSOR]],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo binary sensor."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    monkeypatch.setattr(
        get_data[0].parsed["ABC999111"].motion_sensors["AABBCC"], "motion", False
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_connectivity")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    assert state1.state == STATE_ON
    assert state3.state == STATE_OFF
