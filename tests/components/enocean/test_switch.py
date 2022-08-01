"""Tests for the EnOcean switch platform."""

from unittest.mock import MagicMock, Mock

from enocean.utils import combine_hex

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

# from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.common import MockConfigEntry, assert_setup_component


def mock_switch():
    """Mock an EnOcean switch."""
    dev_info_mock = MagicMock()

    _mock_switch = Mock(
        id="enocean-switch",
        observe=Mock(),
        device_info=dev_info_mock,
    )

    _mock_switch.name = "enocean-switch"
    return _mock_switch


async def test_unique_id_migration(
    hass: HomeAssistant, mock_gateway: MockConfigEntry
) -> None:
    """Test EnOcean switch ID migration."""
    dev_id = [0xDE, 0xAD, 0xBE, 0xEF]
    channel = 1
    ent_reg = er.async_get(hass)

    old_unique_id = f"{combine_hex(dev_id)}"

    entry = MockConfigEntry(domain="enocean", data={"device": "/dev/null"})

    entry.add_to_hass(hass)

    switch_name = "switch.room0"
    entity_name = switch_name.split(".")[1]

    # Add a switch with an old unique_id to the entity registry
    entity_entry = ent_reg.async_get_or_create(
        SWITCH_DOMAIN,
        "enocean",
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )

    assert entity_entry.entity_id == switch_name
    assert entity_entry.unique_id == old_unique_id

    # Now add the sensor to check, whether the old unique_id is migrated
    # switch = mock_switch()

    # mock_gateway.mock_devices.append(switch)

    # switch2 = MockConfigEntry(
    #    domain="enocean",
    #    data={"platform": "switch", "id": dev_id, "channel": 1, "name": "room0"},
    # )

    # switch2.add_to_hass(hass)
    # await async_setup_entry(hass, switch2)
    # await switch2.async_setup(hass)
    # await hass.async_block_till_done()

    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "enocean",
                    "id": dev_id,
                    "channel": 1,
                    "name": "room0",
                }
            },
        )

    await hass.async_block_till_done()

    # Check that new entry has a new unique_id
    entity_entry = ent_reg.async_get(switch_name)
    new_unique_id = f"{combine_hex(dev_id)}{channel}"

    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("switch", "enocean", old_unique_id) is None
