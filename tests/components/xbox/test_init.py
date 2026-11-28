"""Tests for the Xbox integration."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from httpx2 import (
    ConnectTimeout,
    HTTPStatusError,
    ProtocolError,
    RequestError,
    Response,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from pythonxbox.api.provider.smartglass.models import SmartglassConsoleList
from pythonxbox.common.exceptions import AuthenticationException
import respx

from homeassistant.components import automation
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.xbox.binary_sensor import XboxBinarySensor
from homeassistant.components.xbox.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("xbox_live_client")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        ConnectTimeout(""),
        HTTPStatusError("", request=Mock(), response=Mock()),
        ProtocolError(""),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    xbox_live_client.smartglass.get_console_list.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("xbox_live_client")
async def test_config_implementation_not_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test implementation not available."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xbox.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("state", "exception"),
    [
        (
            ConfigEntryState.SETUP_ERROR,
            OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=Mock()),
        ),
        (
            ConfigEntryState.SETUP_RETRY,
            OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=Mock()),
        ),
        (
            ConfigEntryState.SETUP_RETRY,
            ClientError,
        ),
    ],
)
@respx.mock
async def test_oauth_session_refresh_failure_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    state: ConfigEntryState,
    exception: Exception | type[Exception],
    oauth2_session: AsyncMock,
) -> None:
    """Test OAuth2 session refresh failures."""

    oauth2_session.async_ensure_token_valid.side_effect = exception
    oauth2_session.valid_token = False

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


@pytest.mark.parametrize(
    ("state", "exception"),
    [
        (
            ConfigEntryState.SETUP_RETRY,
            HTTPStatusError(
                "", request=MagicMock(), response=Response(HTTPStatus.IM_A_TEAPOT)
            ),
        ),
        (ConfigEntryState.SETUP_RETRY, RequestError("", request=Mock())),
        (ConfigEntryState.SETUP_ERROR, AuthenticationException),
    ],
)
@respx.mock
async def test_oauth_session_refresh_user_and_xsts_token_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    state: ConfigEntryState,
    exception: Exception | type[Exception],
    oauth2_session: AsyncMock,
) -> None:
    """Test OAuth2 user and XSTS token refresh failures."""
    oauth2_session.valid_token = True

    respx.post(OAUTH2_TOKEN).mock(side_effect=exception)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


@pytest.mark.parametrize(
    "exception",
    [
        ConnectTimeout(""),
        HTTPStatusError("", request=Mock(), response=Mock()),
        ProtocolError(""),
    ],
)
@pytest.mark.parametrize(
    ("provider", "method"),
    [
        ("smartglass", "get_console_status"),
        ("catalog", "get_product_from_alternate_id"),
        ("people", "get_friend_by_xuid"),
        ("people", "get_friends_own"),
    ],
)
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
    provider: str,
    method: str,
) -> None:
    """Test coordinator update failed."""

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time
async def test_dynamic_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test adding of new and removal of stale devices at runtime."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
        is None
    )

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
    )

    response = await client.remove_device(device.id)
    assert not response["success"]

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await client.remove_device(device.id)
    assert response["success"]

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
        is None
    )

    # Test that service devices cannot be removed
    assert (
        account := device_registry.async_get_device_by_identifier(
            (DOMAIN, "271958441785640"), config_entry.entry_id
        )
    )
    response = await client.remove_device(account.id)
    assert not response["success"]


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("xuid", "subentry_unique_id"),
    [
        pytest.param("271958441785640", None, id="account"),
        pytest.param("2533274913657542", "2533274913657542", id="friend"),
    ],
)
async def test_binary_sensor_deprecation_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
    xuid: str,
    subentry_unique_id: str | None,
) -> None:
    """Test sensor deprecation issue."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    config_entry.add_to_hass(hass)
    subentry_id = next(
        (
            subentry.subentry_id
            for subentry in config_entry.subentries.values()
            if subentry.unique_id == subentry_unique_id
        ),
        None,
    )
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"{xuid}_{XboxBinarySensor.HAS_GAME_PASS}",
        config_entry=config_entry,
        config_subentry_id=subentry_id,
        suggested_object_id="gsr_ae_subscribed_to_xbox_game_pass",
        disabled_by=None,
    )

    assert entity_registry is not None

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test",
                "alias": "test",
                "trigger": {
                    "platform": "state",
                    "entity_id": f"{BINARY_SENSOR_DOMAIN}.gsr_ae_subscribed_to_xbox_game_pass",
                },
                "action": {
                    "action": "automation.turn_on",
                    "target": {
                        "entity_id": "automation.test",
                    },
                },
            }
        },
    )

    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        entity_registry.async_get(
            f"binary_sensor.{'gsr_ae_subscribed_to_xbox_game_pass'}"
        )
        is not None
    )
    assert (
        repair_issue := issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{xuid}_{XboxBinarySensor.HAS_GAME_PASS}",
        )
    )
    assert repair_issue.config_entry_id == config_entry.entry_id
    assert repair_issue.config_subentry_id == subentry_id

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_entity_{xuid}_{XboxBinarySensor.HAS_GAME_PASS}",
    )

    assert (
        entity_registry.async_get(
            f"binary_sensor.{'gsr_ae_subscribed_to_xbox_game_pass'}"
        )
        is None
    )


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_binary_sensor_deprecation_remove_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we remove a deprecated sensor."""

    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"271958441785640_{XboxBinarySensor.HAS_GAME_PASS}",
        suggested_object_id="gsr_ae_subscribed_to_xbox_game_pass",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert entity_registry is not None

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        entity_registry.async_get(
            f"binary_sensor.{'gsr_ae_subscribed_to_xbox_game_pass'}"
        )
        is None
    )


async def _remove_friend_subentry(
    hass: HomeAssistant, config_entry: MockConfigEntry, subentry_id: str
) -> None:
    """Remove the friend subentry."""
    assert hass.config_entries.async_remove_subentry(config_entry, subentry_id)


async def _remove_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, subentry_id: str
) -> None:
    """Remove the config entry."""
    await hass.config_entries.async_remove(config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("remove_owner", "expected_remaining"),
    [
        pytest.param(_remove_friend_subentry, {"271958441785640"}, id="subentry"),
        pytest.param(_remove_config_entry, set(), id="config_entry"),
    ],
)
async def test_binary_sensor_deprecation_issue_removed_with_owner(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    remove_owner: Callable[
        [HomeAssistant, MockConfigEntry, str], Coroutine[Any, Any, None]
    ],
    expected_remaining: set[str],
) -> None:
    """Test deprecation issues are removed with the subentry or entry owning them."""
    config_entry.add_to_hass(hass)
    friend_subentry_id = next(
        subentry.subentry_id
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == "2533274913657542"
    )
    for xuid, subentry_id in (
        ("271958441785640", None),
        ("2533274913657542", friend_subentry_id),
    ):
        entity_registry.async_get_or_create(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{xuid}_{XboxBinarySensor.HAS_GAME_PASS}",
            config_entry=config_entry,
            config_subentry_id=subentry_id,
            suggested_object_id=f"game_pass_{xuid}",
        )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "id": f"test_{xuid}",
                    "alias": f"test_{xuid}",
                    "trigger": {
                        "platform": "state",
                        "entity_id": f"{BINARY_SENSOR_DOMAIN}.game_pass_{xuid}",
                    },
                    "action": {
                        "action": "automation.turn_on",
                        "target": {"entity_id": f"automation.test_{xuid}"},
                    },
                }
                for xuid in ("271958441785640", "2533274913657542")
            ]
        },
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_ids = {
        xuid: f"deprecated_entity_{xuid}_{XboxBinarySensor.HAS_GAME_PASS}"
        for xuid in ("271958441785640", "2533274913657542")
    }
    assert all(
        issue_registry.async_get_issue(DOMAIN, issue_id)
        for issue_id in issue_ids.values()
    )

    await remove_owner(hass, config_entry, friend_subentry_id)
    await hass.async_block_till_done()

    assert {
        xuid
        for xuid, issue_id in issue_ids.items()
        if issue_registry.async_get_issue(DOMAIN, issue_id)
    } == expected_remaining
