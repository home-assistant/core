"""Test the SFR Box sensors."""
from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sfr_box import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("system_get_info", "dsl_get_info", "wan_get_info")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box sensors."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device({(DOMAIN, "e4:5d:51:00:11:22")})
    assert device_entry == snapshot

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    for entity in entity_entries:
        entity_registry.async_update_entity(entity.entity_id, **{"disabled_by": None})

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    for entity in entity_entries:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)
