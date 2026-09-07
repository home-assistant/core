"""Tests for YouTube."""

import http
import time
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.youtube.const import (
    CONF_CHANNEL_ID,
    CONF_CHANNELS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import MockYouTube
from .conftest import (
    CHANNEL_ID,
    GOOGLE_TOKEN_URI,
    LINUS_CHANNEL_ID,
    TITLE,
    ComponentSetup,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.services.async_services().get(DOMAIN)


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        status=status,
    )

    await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


async def test_expired_token_refresh_client_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test failure while refreshing token with a client error."""

    with patch(
        "homeassistant.components.youtube.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError,
    ):
        await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: ComponentSetup,
) -> None:
    """Test device info."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHANNEL_ID), entry.entry_id
    )

    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, CHANNEL_ID)}
    assert device.manufacturer == "Google, Inc."
    assert device.name == "Google for Developers"


async def test_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    expires_at: int,
) -> None:
    """Test migration of an options based entry to the subentry structure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=CHANNEL_ID,
        version=1,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": "https://www.googleapis.com/auth/youtube.readonly",
            },
        },
        options={CONF_CHANNELS: [CHANNEL_ID]},
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"{entry.entry_id}_{CHANNEL_ID}")},
        manufacturer="Google, Inc.",
        name="Google for Developers",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_{CHANNEL_ID}_subscribers",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="google_for_developers_subscribers",
    )
    # Device and entity left behind by a channel which is no longer tracked,
    # as happened when it was removed from the options before this migration.
    orphan_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"{entry.entry_id}_{LINUS_CHANNEL_ID}")},
        manufacturer="Google, Inc.",
        name="Linus Tech Tips",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_{LINUS_CHANNEL_ID}_subscribers",
        config_entry=entry,
        device_id=orphan_device.id,
        suggested_object_id="linus_tech_tips_subscribers",
    )

    with patch(
        "homeassistant.components.youtube.api.YouTube",
        return_value=MockYouTube(hass),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.options == {}
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == "channel"
    assert subentry.unique_id == CHANNEL_ID
    assert subentry.title == "Google for Developers"
    assert subentry.data == {CONF_CHANNEL_ID: CHANNEL_ID}

    migrated_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHANNEL_ID), entry.entry_id
    )
    assert migrated_device is not None
    assert migrated_device.id == device.id
    assert migrated_device.config_subentry_id == subentry.subentry_id

    # The unique id keeps the entry id prefix so two accounts can track
    # the same channel.
    migrated_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{CHANNEL_ID}_subscribers"
    )
    assert migrated_entity_id is not None
    migrated_entity = entity_registry.async_get(migrated_entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.device_id == device.id

    # The untracked channel's device and entity are cleaned up
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, LINUS_CHANNEL_ID), entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{LINUS_CHANNEL_ID}_subscribers"
        )
        is None
    )
    assert hass.states.get("sensor.google_for_developers_subscribers") is not None


async def test_remove_subentry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: ComponentSetup,
) -> None:
    """Test removing a channel subentry removes its device and entities."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHANNEL_ID), entry.entry_id
    )
    assert device is not None

    hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    await hass.async_block_till_done()

    assert not entry.subentries
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, CHANNEL_ID), entry.entry_id
        )
        is None
    )
    assert hass.states.get("sensor.google_for_developers_subscribers") is None


async def test_setup_fails_when_channel_missing_from_api(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: ComponentSetup,
) -> None:
    """Test the device is kept when the API omits the configured channel."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHANNEL_ID), entry.entry_id
    )
    assert device is not None

    with patch(
        "homeassistant.components.youtube.api.AsyncConfigEntryAuth.get_resource",
        return_value=MockYouTube(hass, channel_fixture="get_no_channel.json"),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, CHANNEL_ID), entry.entry_id
        )
        is not None
    )


async def test_oauth_implementation_not_available(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(
        "homeassistant.components.youtube.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
