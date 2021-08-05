"""Tests for the litejet component."""
from homeassistant.components import scene, switch
from homeassistant.components.litejet import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def async_init_integration(
    hass, use_switch=False, use_scene=False
) -> MockConfigEntry:
    """Set up the LiteJet integration in Home Assistant."""

    registry = er.async_get(hass)

    entry_data = {CONF_PORT: "/dev/mock"}

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=entry_data[CONF_PORT], data=entry_data
    )

    if use_switch:
        registry.async_get_or_create(
            switch.DOMAIN,
            DOMAIN,
            f"{entry.entry_id}_1",
            suggested_object_id="mock_switch_1",
            disabled_by=None,
        )
        registry.async_get_or_create(
            switch.DOMAIN,
            DOMAIN,
            f"{entry.entry_id}_2",
            suggested_object_id="mock_switch_2",
            disabled_by=None,
        )

    if use_scene:
        registry.async_get_or_create(
            scene.DOMAIN,
            DOMAIN,
            f"{entry.entry_id}_1",
            suggested_object_id="mock_scene_1",
            disabled_by=None,
        )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
