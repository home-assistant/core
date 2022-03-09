"""The tests for the Light Switch platform."""
import pytest

from homeassistant.components.switch_as_x import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("entity_type", ("light",))
async def test_config_entry(hass: HomeAssistant, entity_type):
    """Test light switch setup from config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": "switch.abc", "entity_type": entity_type},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.config.components

    state = hass.states.get(f"{entity_type}.abc")
    assert state.state == "unavailable"
    # Name copied from config entry title
    assert state.name == "ABC"

    # Check the light is added to the entity registry
    registry = er.async_get(hass)
    entity_entry = registry.async_get(f"{entity_type}.abc")
    assert entity_entry.unique_id == config_entry.entry_id


@pytest.mark.parametrize("entity_type", ("light",))
async def test_config_entry_uuid(hass: HomeAssistant, entity_type):
    """Test light switch setup from config entry with entity registry id."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create("switch", "test", "unique")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": registry_entry.id, "entity_type": entity_type},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{entity_type}.abc")


async def test_config_entry_unregistered_uuid(hass: HomeAssistant):
    """Test light switch setup from config entry with unknown entity registry id."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"entity_id": fake_uuid},
        title="ABC",
    )

    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
