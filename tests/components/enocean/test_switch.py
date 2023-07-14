"""Tests for the EnOcean switch platform."""

from enocean.utils import combine_hex

from homeassistant.components.enocean import DOMAIN as ENOCEAN_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component

SWITCH_CONFIG = {
    "switch": [
        {
            "platform": ENOCEAN_DOMAIN,
            "id": [0xDE, 0xAD, 0xBE, 0xEF],
            "channel": 1,
            "name": "room0",
        },
    ]
}


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test EnOcean switch ID migration."""

    entity_name = SWITCH_CONFIG["switch"][0]["name"]
    switch_entity_id = f"{SWITCH_DOMAIN}.{entity_name}"
    dev_id = SWITCH_CONFIG["switch"][0]["id"]
    channel = SWITCH_CONFIG["switch"][0]["channel"]

    ent_reg = er.async_get(hass)

    old_unique_id = f"{combine_hex(dev_id)}"

    entry = MockConfigEntry(domain=ENOCEAN_DOMAIN, data={"device": "/dev/null"})

    entry.add_to_hass(hass)

    # Add a switch with an old unique_id to the entity registry
    entity_entry = ent_reg.async_get_or_create(
        SWITCH_DOMAIN,
        ENOCEAN_DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )

    assert entity_entry.entity_id == switch_entity_id
    assert entity_entry.unique_id == old_unique_id

    # Now add the sensor to check, whether the old unique_id is migrated

    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            SWITCH_CONFIG,
        )

    await hass.async_block_till_done()

    # Check that new entry has a new unique_id
    entity_entry = ent_reg.async_get(switch_entity_id)
    new_unique_id = f"{combine_hex(dev_id)}-{channel}"

    assert entity_entry.unique_id == new_unique_id
    assert (
        ent_reg.async_get_entity_id(SWITCH_DOMAIN, ENOCEAN_DOMAIN, old_unique_id)
        is None
    )
