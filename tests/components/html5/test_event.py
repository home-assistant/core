"""Tests for the HTML5 event platform."""

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp.hdrs import AUTHORIZATION
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.html5.const import DOMAIN
from homeassistant.components.html5.notify import ATTR_ACTION, ATTR_TAG, ATTR_TYPE
from homeassistant.components.notify import ATTR_DATA, ATTR_TARGET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .test_notify import SUBSCRIPTION_1

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.fixture
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.html5.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid", "event_only")
@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    load_config: MagicMock,
) -> None:
    """Snapshot test states of event platform."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("event_payload"),
    [
        {
            ATTR_TARGET: "my-desktop",
            ATTR_TYPE: "clicked",
            ATTR_ACTION: "open_app",
            ATTR_TAG: "1234",
            ATTR_DATA: {"customKey": "Value"},
        },
        {
            ATTR_TARGET: "my-desktop",
            ATTR_TYPE: "received",
            ATTR_TAG: "1234",
            ATTR_DATA: {"customKey": "Value"},
        },
        {
            ATTR_TARGET: "my-desktop",
            ATTR_TYPE: "closed",
            ATTR_TAG: "1234",
            ATTR_DATA: {"customKey": "Value"},
        },
    ],
)
@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_events(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    event_payload: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_jwt: MagicMock,
) -> None:
    """Test events."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("event.my_desktop")) is not None
    assert state.state == STATE_UNKNOWN

    client = await hass_client()

    mock_jwt.decode.return_value = {ATTR_TARGET: event_payload[ATTR_TARGET]}

    resp = await client.post(
        "/api/notify.html5/callback",
        json=event_payload,
        headers={AUTHORIZATION: "Bearer JWT"},
    )

    assert resp.status == HTTPStatus.OK

    assert (state := hass.states.get("event.my_desktop"))
    assert state.state == "1970-01-01T00:00:00.000+00:00"
    assert state.attributes.get("action") == event_payload.get(ATTR_ACTION)
    assert state.attributes.get("tag") == event_payload[ATTR_TAG]
    assert state.attributes.get("customKey") == event_payload[ATTR_DATA]["customKey"]


@pytest.mark.parametrize("event_type", ["clicked", "received", "closed"])
@pytest.mark.usefixtures("mock_wp", "mock_jwt", "mock_vapid", "mock_uuid")
async def test_deprecation_event_bus(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    event_type: str,
) -> None:
    """Test deprecation of events on the event bus."""
    load_config.return_value = {"device": SUBSCRIPTION_1}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    config_entry.async_on_unload(
        hass.bus.async_listen(f"html5_notification.{event_type}", lambda _: None)
    )
    client = await hass_client()

    resp = await client.post(
        "/api/notify.html5/callback",
        json={"type": event_type, "tag": "12345", "target": "device"},
        headers={AUTHORIZATION: "Bearer JWT"},
    )

    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body == {"event": event_type, "status": "ok"}

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"deprecated_event_bus_html5_notification.{event_type}",
    )


@pytest.mark.parametrize("event_type", ["clicked", "received", "closed"])
@pytest.mark.usefixtures("mock_wp", "mock_jwt", "mock_vapid", "mock_uuid")
async def test_deprecation_event_bus_no_listeners(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    event_type: str,
) -> None:
    """Test no issue is created when there are no listeners."""
    load_config.return_value = {"device": SUBSCRIPTION_1}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    resp = await client.post(
        "/api/notify.html5/callback",
        json={"type": event_type, "tag": "12345", "target": "device"},
        headers={AUTHORIZATION: "Bearer JWT"},
    )

    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body == {"event": event_type, "status": "ok"}

    assert not issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"deprecated_event_bus_html5_notification.{event_type}",
    )
