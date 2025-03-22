"""The tests for the Sun binary_sensor platform."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import sun
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setting_rising(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test retrieving sun setting and rising."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(utc_now)
    await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.sun_solar_rising").state == "on"

    entry_ids = hass.config_entries.async_entries("sun")

    freezer.tick(timedelta(hours=12))
    # Block once for Sun to update
    await hass.async_block_till_done()
    # Block another time for the sensors to update
    await hass.async_block_till_done()

    # Make sure all the signals work
    assert hass.states.get("binary_sensor.sun_solar_rising").state == "off"

    entity = entity_registry.async_get("binary_sensor.sun_solar_rising")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-binary-solar_rising"
