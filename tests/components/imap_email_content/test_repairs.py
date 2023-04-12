"""Test repairs for imap_email_content."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    """Mock the imap client."""
    with patch(
        "homeassistant.components.imap_email_content.sensor.EmailReader.read_next",
        return_value=None,
    ), patch("imaplib.IMAP4_SSL") as mock_imap_client:
        yield mock_imap_client


CONFIG = {
    "platform": "imap_email_content",
    "name": "Notifications",
    "server": "imap.example.com",
    "port": 993,
    "username": "john.doe@example.com",
    "password": "**SECRET**",
    "folder": "INBOX.Notifications",
    "value_template": "{{ body }}",
    "senders": ["company@example.com"],
}
DESCRIPTION_PLACEHOLDERS = {
    "yaml_example": ""
    "template:\n"
    "- sensor:\n"
    "  - name: Notifications\n"
    "    state: '{{ trigger.event.data[\"text\"] }}'\n"
    "  trigger:\n  - event_data:\n"
    "      sender: company@example.com\n"
    "    event_type: imap_content\n"
    "    id: custom_event\n"
    "    platform: event\n",
    "server": "imap.example.com",
    "port": 993,
    "username": "john.doe@example.com",
    "password": "**SECRET**",
    "folder": "INBOX.Notifications",
    "value_template": '{{ trigger.event.data["text"] }}',
    "name": "Notifications",
}

CONFIG_DEFAULT = {
    "platform": "imap_email_content",
    "name": "Notifications",
    "server": "imap.example.com",
    "port": 993,
    "username": "john.doe@example.com",
    "password": "**SECRET**",
    "folder": "INBOX.Notifications",
    "senders": ["company@example.com"],
}
DESCRIPTION_PLACEHOLDERS_DEFAULT = {
    "yaml_example": ""
    "template:\n"
    "- sensor:\n"
    "  - name: Notifications\n"
    "    state: '{{ trigger.event.data[\"subject\"] }}'\n"
    "  trigger:\n  - event_data:\n"
    "      sender: company@example.com\n"
    "    event_type: imap_content\n"
    "    id: custom_event\n"
    "    platform: event\n",
    "server": "imap.example.com",
    "port": 993,
    "username": "john.doe@example.com",
    "password": "**SECRET**",
    "folder": "INBOX.Notifications",
    "value_template": '{{ trigger.event.data["subject"] }}',
    "name": "Notifications",
}


@pytest.mark.parametrize(
    ("config", "description_placeholders"),
    [
        (CONFIG, DESCRIPTION_PLACEHOLDERS),
        (CONFIG_DEFAULT, DESCRIPTION_PLACEHOLDERS_DEFAULT),
    ],
    ids=["with_value_template", "default_subject"],
)
async def test_deprecation_repair_flow(
    hass: HomeAssistant,
    mock_client: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    config: str | None,
    description_placeholders: str,
) -> None:
    """Test the deprecation repair flow."""
    # setup config
    await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.notifications")
    assert state is not None

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})

    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["domain"] == "imap_email_content":
            issue = i
    assert issue is not None
    assert (
        issue["issue_id"]
        == "Notifications_john.doe@example.com_imap.example.com_INBOX.Notifications"
    )
    assert issue["is_fixable"]
    url = RepairsFlowIndexView.url
    resp = await client.post(
        url, json={"handler": "imap_email_content", "issue_id": issue["issue_id"]}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == description_placeholders
    assert data["step_id"] == "start"

    # Apply fix
    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == description_placeholders
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client, patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ):
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


@pytest.mark.parametrize(
    ("config", "description_placeholders"),
    [
        (CONFIG, DESCRIPTION_PLACEHOLDERS),
        (CONFIG_DEFAULT, DESCRIPTION_PLACEHOLDERS_DEFAULT),
    ],
    ids=["with_value_template", "default_subject"],
)
async def test_repair_flow_where_entry_already_exists(
    hass: HomeAssistant,
    mock_client: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    config: str | None,
    description_placeholders: str,
) -> None:
    """Test the deprecation repair flow and an entry already exists."""

    await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.notifications")
    assert state is not None

    existing_imap_entry_config = {
        "username": "john.doe@example.com",
        "password": "password",
        "server": "imap.example.com",
        "port": 993,
        "charset": "utf-8",
        "folder": "INBOX.Notifications",
        "search": "UnSeen UnDeleted",
    }

    with patch("homeassistant.components.imap.async_setup_entry", return_value=True):
        imap_entry = MockConfigEntry(domain="imap", data=existing_imap_entry_config)
        imap_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(imap_entry.entry_id)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})

    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["domain"] == "imap_email_content":
            issue = i
    assert issue is not None
    assert (
        issue["issue_id"]
        == "Notifications_john.doe@example.com_imap.example.com_INBOX.Notifications"
    )
    assert issue["is_fixable"]
    assert issue["translation_key"] == "migration"

    url = RepairsFlowIndexView.url
    resp = await client.post(
        url, json={"handler": "imap_email_content", "issue_id": issue["issue_id"]}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == description_placeholders
    assert data["step_id"] == "start"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == description_placeholders
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client, patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ):
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "abort"
    assert data["reason"] == "already_configured"

    # We should now have a non_fixable issue left since there is still
    # a config in configuration.yaml
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["domain"] == "imap_email_content":
            issue = i
    assert issue is not None
    assert (
        issue["issue_id"]
        == "Notifications_john.doe@example.com_imap.example.com_INBOX.Notifications"
    )
    assert not issue["is_fixable"]
    assert issue["translation_key"] == "deprecation"
