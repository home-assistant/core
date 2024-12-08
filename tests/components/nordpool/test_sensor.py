"""The test for the Nord Pool sensor platform."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Nord Pool sensor."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


@pytest.mark.freeze_time("2024-11-05T23:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_no_next_price(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Nord Pool sensor."""

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")

    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.28914"
    assert last_price.state == "0.28914"
    assert next_price.state == STATE_UNKNOWN


@pytest.mark.freeze_time("2024-11-05T00:00:00+01:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_no_previous_price(
    hass: HomeAssistant, load_int: ConfigEntry
) -> None:
    """Test the Nord Pool sensor."""

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")

    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.25073"
    assert last_price.state == STATE_UNKNOWN
    assert next_price.state == "0.07636"
