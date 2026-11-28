"""Tests for the Kodi notify platform."""

import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import jsonrpc_async
from jsonrpc_base.jsonrpc import TransportError
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kodi.const import DOMAIN
from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntryDisabler
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

ENTITY_ID = "notify.name"
YAML_NOTIFY = {
    "platform": DOMAIN,
    "name": "living_room",
    "host": "1.1.1.1",
    "port": 8080,
    "username": "user",
    "password": "pass",
}

NOTIFY_CONFIG = {
    NOTIFY_DOMAIN: {
        "platform": "kodi",
        "name": "kodi",
        "host": "1.1.1.1",
        "port": 8080,
    }
}


async def setup_notify(hass: HomeAssistant, server: AsyncMock) -> None:
    """Set up the Kodi notify platform with a mocked server."""
    with patch("jsonrpc_async.Server", return_value=server):
        assert await async_setup_component(hass, NOTIFY_DOMAIN, NOTIFY_CONFIG)
        await hass.async_block_till_done()


async def test_send_message(hass: HomeAssistant) -> None:
    """Test sending a notification to Kodi."""
    server = AsyncMock()
    await setup_notify(hass, server)

    await hass.services.async_call(
        NOTIFY_DOMAIN, "kodi", {"message": "Hello", "title": "Test"}, blocking=True
    )

    server.GUI.ShowNotification.assert_called_once_with("Test", "Hello", "info", 10000)


async def test_send_message_transport_error(hass: HomeAssistant) -> None:
    """Test an unreachable Kodi raises an error instead of only logging."""
    server = AsyncMock()
    server.GUI.ShowNotification.side_effect = jsonrpc_async.TransportError(
        "Unable to connect"
    )
    await setup_notify(hass, server)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "kodi", {"message": "Hello"}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "notify_failed"


async def setup_yaml_notify(
    hass: HomeAssistant, yaml_notify: list[dict[str, Any]]
) -> None:
    """Set up the notify integration from YAML, which also sets up Kodi."""
    with patch("jsonrpc_async.Server", return_value=AsyncMock()):
        assert await async_setup_component(
            hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: yaml_notify}
        )
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_notify_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the notify entity of a Kodi config entry."""
    with patch("homeassistant.components.kodi.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_connection")
async def test_notify_entity_send_message(
    hass: HomeAssistant,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sending a notification with the notify.send_message action."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, "message": "Hello", "title": "Test"},
        blocking=True,
    )

    mock_kodi.send_notification.assert_called_once_with("Test", "Hello", "info", 10000)


@pytest.mark.parametrize(
    ("service_data", "expected_call"),
    [
        pytest.param(
            {"message": "Hello"},
            ("Home Assistant", "Hello", "info", 10000),
            id="defaults",
        ),
        pytest.param(
            {
                "message": "Hello",
                "title": "Test",
                "icon": "warning",
                "displaytime": 5000,
            },
            ("Test", "Hello", "warning", 5000),
            id="all_options",
        ),
    ],
)
@pytest.mark.usefixtures("mock_connection")
async def test_kodi_send_message_action(
    hass: HomeAssistant,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    service_data: dict[str, Any],
    expected_call: tuple[str, str, str, int],
) -> None:
    """Test the kodi.send_message entity action."""
    freezer.move_to("2026-10-29T12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_kodi.send_notification.assert_called_once_with(*expected_call)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "2026-10-29T12:00:00+00:00"


@pytest.mark.usefixtures("mock_connection")
async def test_kodi_send_message_action_invalid(
    hass: HomeAssistant,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the kodi.send_message action rejects a too short display time."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, "message": "Hello", "displaytime": 1000},
            blocking=True,
        )

    mock_kodi.send_notification.assert_not_called()


@pytest.mark.parametrize("domain", [NOTIFY_DOMAIN, DOMAIN])
@pytest.mark.usefixtures("mock_connection")
async def test_notify_entity_send_message_error(
    hass: HomeAssistant,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
    domain: str,
) -> None:
    """Test an unreachable Kodi raises an error from the notify entity."""
    await setup_integration(hass, mock_config_entry)
    mock_kodi.send_notification.side_effect = TransportError("Unable to connect")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            domain,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, "message": "Hello"},
            blocking=True,
        )

    assert err.value.translation_key == "notify_failed"
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("yaml_notify", "entity_id", "action"),
    [
        pytest.param(
            YAML_NOTIFY, "notify.living_room", "notify.living_room", id="name"
        ),
        pytest.param(
            {**YAML_NOTIFY, "host": "http://1.1.1.1"},
            "notify.living_room",
            "notify.living_room",
            id="host_with_scheme",
        ),
        pytest.param(
            {key: value for key, value in YAML_NOTIFY.items() if key != "name"},
            ENTITY_ID,
            "notify.notify",
            id="without_name",
        ),
    ],
)
@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_yaml_notify_linked_to_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    yaml_notify: dict[str, Any],
    entity_id: str,
    action: str,
) -> None:
    """Test a matching YAML notify platform names the notify entity of the entry."""
    mock_config_entry.add_to_hass(hass)

    await setup_yaml_notify(hass, [yaml_notify])

    assert hass.states.get(entity_id)
    # The YAML keeps providing the legacy action until it is removed
    assert hass.services.has_service(NOTIFY_DOMAIN, action.split(".")[1])
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_notify_{action.split('.')[1]}"
    )
    assert issue
    assert issue.translation_key == "deprecated_yaml_notify_entity"
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "action": action,
        "entity_id": entity_id,
        "title": "name",
    }


@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_yaml_notify_several_platforms_one_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the first YAML name names the entity and every platform gets an issue."""
    mock_config_entry.add_to_hass(hass)

    await setup_yaml_notify(hass, [YAML_NOTIFY, {**YAML_NOTIFY, "name": "bedroom"}])

    for name in ("living_room", "bedroom"):
        issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_yaml_notify_{name}")
        assert issue
        assert issue.translation_placeholders["entity_id"] == "notify.living_room"


@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_yaml_notify_existing_entity_keeps_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an existing notify entity is not renamed after the YAML name."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        NOTIFY_DOMAIN,
        DOMAIN,
        mock_config_entry.unique_id,
        config_entry=mock_config_entry,
        suggested_object_id="name",
    )

    await setup_yaml_notify(hass, [YAML_NOTIFY])

    assert hass.states.get(ENTITY_ID)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_notify_living_room")
    assert issue
    assert issue.translation_placeholders["entity_id"] == ENTITY_ID


@pytest.mark.parametrize(
    "yaml_notify",
    [
        pytest.param({**YAML_NOTIFY, "host": "2.2.2.2"}, id="other_host"),
        pytest.param({**YAML_NOTIFY, "port": 8081}, id="other_port"),
        pytest.param({**YAML_NOTIFY, "username": "other"}, id="other_username"),
        pytest.param({**YAML_NOTIFY, "password": "other"}, id="other_password"),
    ],
)
@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_yaml_notify_without_matching_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    yaml_notify: dict[str, Any],
) -> None:
    """Test a YAML notify platform without a matching entry raises an issue."""
    mock_config_entry.add_to_hass(hass)

    await setup_yaml_notify(hass, [yaml_notify])

    # The entry still gets its notify entity, named after the device
    assert hass.states.get(ENTITY_ID)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_notify_living_room")
    assert issue
    assert issue.translation_key == "deprecated_yaml_notify_no_entry"
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "action": "notify.living_room",
        "url": "https://www.home-assistant.io/integrations/kodi/",
    }


@pytest.mark.parametrize(
    "yaml_notify",
    [
        pytest.param(None, id="empty"),
        pytest.param({"platform": DOMAIN}, id="without_host"),
        pytest.param({**YAML_NOTIFY, "port": "invalid"}, id="invalid_port"),
        pytest.param({**YAML_NOTIFY, "port": math.inf}, id="infinite_port"),
        pytest.param({**YAML_NOTIFY, "name": ["living_room"]}, id="name_list"),
        pytest.param(
            {key: value for key, value in YAML_NOTIFY.items() if key != "password"},
            id="username_without_password",
        ),
    ],
)
async def test_yaml_notify_invalid(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    yaml_notify: dict[str, Any] | None,
) -> None:
    """Test unvalidated invalid YAML notify blocks don't raise an issue."""
    assert await async_setup_component(hass, DOMAIN, {NOTIFY_DOMAIN: [yaml_notify]})
    await hass.async_block_till_done()

    assert not [key for key in issue_registry.issues if key[0] == DOMAIN]


async def test_yaml_notify_with_ignored_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an ignored discovery entry does not match a YAML notify platform."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, data={}).add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {NOTIFY_DOMAIN: [YAML_NOTIFY]})
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_notify_living_room")
    assert issue
    assert issue.translation_key == "deprecated_yaml_notify_no_entry"


async def test_yaml_notify_with_disabled_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a matching disabled entry asks to enable the Kodi device."""
    MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    await setup_yaml_notify(hass, [YAML_NOTIFY])

    # The YAML keeps providing the legacy action until it is removed
    assert hass.services.has_service(NOTIFY_DOMAIN, "living_room")
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_notify_living_room")
    assert issue
    assert issue.translation_key == "deprecated_yaml_notify_entry_disabled"
    assert issue.translation_placeholders == {
        "action": "notify.living_room",
        "title": "name",
    }
