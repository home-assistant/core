"""Test sensor of Brother integration."""

from datetime import timedelta
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.brother.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import async_fire_time_changed, load_fixture, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test states of the sensors."""
    hass.config.set_time_zone("UTC")
    freezer.move_to("2024-04-20 12:00:00+00:00")

    with patch("homeassistant.components.brother.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "waiting"

    future = utcnow() + timedelta(minutes=5)
    with (
        patch("brother.Brother.initialize"),
        patch("brother.Brother._get_data", side_effect=ConnectionError()),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=10)
    with (
        patch("brother.Brother.initialize"),
        patch(
            "brother.Brother._get_data",
            return_value=json.loads(load_fixture("printer_data.json", "brother")),
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass)

    data = json.loads(load_fixture("printer_data.json", "brother"))

    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.brother.Brother.async_update", return_value=data
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.hl_l2340dw_status"]},
            blocking=True,
        )

        assert len(mock_update.mock_calls) == 1


async def test_unique_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the unique_id migration."""

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "0123456789_b/w_counter",
        suggested_object_id="hl_l2340dw_b_w_counter",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("sensor.hl_l2340dw_b_w_counter")
    assert entry
    assert entry.unique_id == "0123456789_bw_counter"
