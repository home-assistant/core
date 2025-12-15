"""Test the ekey bionyx event platform."""

from http import HTTPStatus

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_event_entity_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test event entity is set up correctly."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that entity was created
    entity_id = "event.test1"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_event_type_attribute(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test event entity has correct event_types attribute."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "event.test1"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check event_types attribute
    event_types = state.attributes.get(ATTR_EVENT_TYPES)
    assert event_types is not None
    assert event_types == ["event happened"]


async def test_config_entry_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry can be unloaded."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Verify entity exists
    entity_id = "event.test1"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Unload config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Entity should become unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_webhook_handler_triggers_event(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test webhook handler triggers event via HTTP request."""
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, "webhook", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "event.test1"
    webhook_data = config_entry.data["webhooks"][0]

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{webhook_data['webhook_id']}",
        json={"auth": webhook_data["auth"]},
    )
    assert response.status == HTTPStatus.OK

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in (STATE_UNKNOWN, None)
    assert state.attributes.get(ATTR_EVENT_TYPE) == "event happened"
