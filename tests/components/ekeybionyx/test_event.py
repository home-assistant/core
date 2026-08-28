"""Test the ekey bionyx event platform."""

from http import HTTPStatus

from aiohttp.test_utils import TestClient

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_event_entity_setup(
    hass: HomeAssistant, load_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test event entity is set up correctly."""
    # Check that entity was created
    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_event_types_attribute(
    hass: HomeAssistant, load_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test event entity has correct event_types attribute."""
    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None

    # Check event_types attribute
    event_types = state.attributes.get(ATTR_EVENT_TYPES)
    assert event_types is not None
    assert event_types == ["event happened"]


async def test_config_entry_unload(
    hass: HomeAssistant,
    load_config_entry: None,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry can be unloaded."""
    assert config_entry.state is ConfigEntryState.LOADED

    # Verify entity exists
    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Unload config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Entity should become unavailable
    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_webhook_handler_triggers_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webhook_test_env: TestClient,
) -> None:
    """Test webhook handler triggers event via HTTP request."""
    webhook_data = config_entry.data["webhooks"][0]

    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    response = await webhook_test_env.post(
        f"/api/webhook/{webhook_data['webhook_id']}",
        json={"auth": webhook_data["auth"]},
    )
    assert response.status == HTTPStatus.OK

    await hass.async_block_till_done()

    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state not in (STATE_UNKNOWN, None)
    assert state.attributes.get(ATTR_EVENT_TYPE) == "event happened"


async def test_webhook_handler_rejects_invalid_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webhook_test_env: TestClient,
) -> None:
    """Test webhook handler ignores requests with invalid auth."""
    webhook_data = config_entry.data["webhooks"][0]

    response = await webhook_test_env.post(
        f"/api/webhook/{webhook_data['webhook_id']}",
        json={"auth": "invalid"},
    )
    assert response.status == HTTPStatus.UNAUTHORIZED

    await hass.async_block_till_done()

    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_webhook_handler_missing_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webhook_test_env: TestClient,
) -> None:
    """Test webhook handler requires the auth field."""
    webhook_data = config_entry.data["webhooks"][0]

    response = await webhook_test_env.post(
        f"/api/webhook/{webhook_data['webhook_id']}",
        json={"not_auth": "value"},
    )
    assert response.status == HTTPStatus.BAD_REQUEST

    await hass.async_block_till_done()

    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_webhook_handler_invalid_json(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webhook_test_env: TestClient,
) -> None:
    """Test webhook handler rejects invalid JSON payloads."""
    webhook_data = config_entry.data["webhooks"][0]

    response = await webhook_test_env.post(
        f"/api/webhook/{webhook_data['webhook_id']}",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status == HTTPStatus.BAD_REQUEST

    await hass.async_block_till_done()

    state = hass.states.get(f"event.{config_entry.data['webhooks'][0]['name']}")
    assert state is not None
    assert state.state == STATE_UNKNOWN
