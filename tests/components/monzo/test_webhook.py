"""Tests for Monzo webhooks and transaction event entities."""

import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError, Webhook
import pytest

from homeassistant.components import cloud
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.monzo.const import (
    ATTR_DATA,
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_URL,
    DOMAIN,
    EVENT_TRANSACTION_CREATED,
    MONZO_WEBHOOK_TRANSACTION_CREATED,
)
from homeassistant.components.monzo.webhook import WEBHOOK_RETRY_DELAY
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.webhook import async_generate_path
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    async_get_config_entry_implementation,
)
from homeassistant.helpers.network import NoURLAvailableError

from . import setup_integration
from .conftest import TEST_ACCOUNTS, WEBHOOK_ID, WEBHOOK_URL

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_cloud_connection_status,
)
from tests.typing import ClientSessionGenerator

CLOUDHOOK_URL = "https://hooks.nabu.casa/test-cloudhook"
NEW_CLOUDHOOK_URL = "https://hooks.nabu.casa/new-cloudhook"
NEW_WEBHOOK_URL = f"https://new.example.com/api/webhook/{WEBHOOK_ID}"
TRANSACTION = {
    "account_id": "acc_curr",
    "amount": -350,
    "currency": "GBP",
    "description": "Ozone Coffee Roasters",
    "merchant": {
        "id": "merchant-id",
        "name": "The De Beauvoir Deli Co.",
        "logo": "https://example.com/logo.png",
        "address": {
            "city": "London",
            "latitude": 51.54151,
            "longitude": -0.084824,
        },
    },
    "unknown_future_field": {"nested": [1, 2, 3]},
}


async def test_registers_one_remote_webhook_per_account(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test every account is registered against the same callback URL."""
    await setup_integration(hass, polling_config_entry)

    assert monzo.user_account.list_account_webhooks.await_args_list == [
        call("acc_curr"),
        call("acc_flex"),
    ]
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", WEBHOOK_URL),
        call("acc_flex", WEBHOOK_URL),
    ]
    assert polling_config_entry.data[CONF_WEBHOOK_URL] == WEBHOOK_URL


async def test_new_account_event_and_webhook_are_discovered(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a newly discovered account gets an event entity and webhook."""
    await setup_integration(hass, polling_config_entry)
    new_account = {
        "id": "acc_joint",
        "name": "Joint Account",
        "type": "uk_retail_joint",
        "balance": {"balance": 456, "total_balance": 654, "currency": "GBP"},
    }
    monzo.user_account.accounts.return_value = [*TEST_ACCOUNTS, new_account]
    monzo.user_account.list_account_webhooks.reset_mock()
    monzo.user_account.list_account_webhooks.side_effect = [
        [Webhook("webhook-acc_curr", "acc_curr", WEBHOOK_URL)],
        [Webhook("webhook-acc_flex", "acc_flex", WEBHOOK_URL)],
        [],
    ]
    monzo.user_account.register_webhook.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        EVENT_DOMAIN, DOMAIN, "acc_joint_transaction"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
    monzo.user_account.register_webhook.assert_awaited_once_with(
        "acc_joint", WEBHOOK_URL
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert monzo.user_account.list_account_webhooks.await_count == 3
    monzo.user_account.register_webhook.assert_awaited_once_with(
        "acc_joint", WEBHOOK_URL
    )


async def test_account_discovered_during_initial_webhook_registration(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test accounts discovered during initial registration get a webhook."""
    registration_started = asyncio.Event()
    continue_registration = asyncio.Event()
    registered_webhooks: dict[str, list[Webhook]] = {}

    async def list_webhooks(account_id: str) -> list[Webhook]:
        if account_id == "acc_curr" and not registration_started.is_set():
            registration_started.set()
            await continue_registration.wait()
        return registered_webhooks.get(account_id, [])

    async def register_webhook(account_id: str, url: str) -> Webhook:
        registered = Webhook(f"webhook-{account_id}", account_id, url)
        registered_webhooks[account_id] = [registered]
        return registered

    monzo.user_account.list_account_webhooks.side_effect = list_webhooks
    monzo.user_account.register_webhook.side_effect = register_webhook
    setup_task = hass.async_create_task(
        setup_integration(hass, polling_config_entry), "set up Monzo"
    )
    await registration_started.wait()

    new_account = {
        "id": "acc_joint",
        "name": "Joint Account",
        "type": "uk_retail_joint",
        "balance": {"balance": 456, "total_balance": 654, "currency": "GBP"},
    }
    monzo.user_account.accounts.return_value = [*TEST_ACCOUNTS, new_account]
    resource_discovered = asyncio.Event()
    hass.bus.async_listen_once(
        er.EVENT_ENTITY_REGISTRY_UPDATED, lambda _: resource_discovered.set()
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await resource_discovered.wait()
    continue_registration.set()
    await setup_task
    await hass.async_block_till_done()

    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", WEBHOOK_URL),
        call("acc_flex", WEBHOOK_URL),
        call("acc_joint", WEBHOOK_URL),
    ]


async def test_removed_account_entities_are_removed(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed account loses its device and entities."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.accounts.return_value = [TEST_ACCOUNTS[0]]
    monzo.user_account.list_account_webhooks.reset_mock()
    monzo.user_account.register_webhook.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "acc_flex"), polling_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            EVENT_DOMAIN, DOMAIN, "acc_flex_transaction"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, "acc_flex_balance")
        is None
    )
    monzo.user_account.list_account_webhooks.assert_not_awaited()
    monzo.user_account.register_webhook.assert_not_awaited()


async def test_registers_non_https_remote_webhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test Monzo webhooks do not require HTTPS or a standard port."""
    webhook_url = f"http://example.com:8123/api/webhook/{WEBHOOK_ID}"
    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        return_value=webhook_url,
    ):
        await setup_integration(hass, polling_config_entry)

    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", webhook_url),
        call("acc_flex", webhook_url),
    ]


async def test_reuses_webhook_and_removes_exact_duplicate(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test an existing callback is reused without touching unrelated hooks."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [
            Webhook("keep", "acc_curr", WEBHOOK_URL),
            Webhook("duplicate", "acc_curr", WEBHOOK_URL),
            Webhook("unrelated", "acc_curr", "https://other.example/webhook"),
        ],
        [],
    ]

    await setup_integration(hass, polling_config_entry)

    monzo.user_account.delete_webhook.assert_awaited_once_with("duplicate")
    monzo.user_account.register_webhook.assert_awaited_once_with(
        "acc_flex", WEBHOOK_URL
    )


async def test_reuses_previously_persisted_webhooks(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test persisted matching callbacks are reused on startup."""
    polling_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        polling_config_entry,
        data={**polling_config_entry.data, CONF_WEBHOOK_URL: WEBHOOK_URL},
    )
    monzo.user_account.list_account_webhooks.side_effect = [
        [Webhook("current", "acc_curr", WEBHOOK_URL)],
        [Webhook("flex", "acc_flex", WEBHOOK_URL)],
    ]

    assert await hass.config_entries.async_setup(polling_config_entry.entry_id)

    monzo.user_account.register_webhook.assert_not_awaited()
    monzo.user_account.delete_webhook.assert_not_awaited()


async def test_replaces_previous_owned_url(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test a previously persisted callback is replaced account by account."""
    old_url = "https://old.example/api/webhook/test-webhook-id"
    polling_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        polling_config_entry,
        data={**polling_config_entry.data, CONF_WEBHOOK_URL: old_url},
    )
    monzo.user_account.list_account_webhooks.side_effect = [
        [Webhook("old-current", "acc_curr", old_url)],
        [Webhook("old-flex", "acc_flex", old_url)],
    ]

    assert await hass.config_entries.async_setup(polling_config_entry.entry_id)

    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", WEBHOOK_URL),
        call("acc_flex", WEBHOOK_URL),
    ]


async def test_partial_registration_is_rolled_back(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test registrations are rolled back when a later account fails."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [],
        InvalidMonzoAPIResponseError(),
    ]

    await setup_integration(hass, polling_config_entry)

    monzo.user_account.register_webhook.assert_awaited_once_with(
        "acc_curr", WEBHOOK_URL
    )
    monzo.user_account.delete_webhook.assert_awaited_once_with("webhook-acc_curr")
    assert CONF_WEBHOOK_URL not in polling_config_entry.data


async def test_rollback_failure_does_not_abort_setup(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test rollback failure is contained while registration is retried."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [],
        InvalidMonzoAPIResponseError(),
    ]
    monzo.user_account.delete_webhook.side_effect = ClientError

    await setup_integration(hass, polling_config_entry)

    assert polling_config_entry.state is ConfigEntryState.LOADED
    monzo.user_account.delete_webhook.assert_awaited_once_with("webhook-acc_curr")
    assert "Unable to roll back Monzo webhook webhook-acc_curr" in caplog.text


async def test_transaction_payload_is_preserved_and_data_is_refreshed(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test the complete transaction reaches the correct event entity."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.accounts.reset_mock()
    monzo.user_account.pots.reset_mock()
    client = await hass_client_no_auth()

    response = await client.post(
        async_generate_path(WEBHOOK_ID),
        json={"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: TRANSACTION},
    )
    assert response.status == 200

    state = hass.states.get("event.current_account_transaction")
    assert state is not None
    assert state.attributes["event_type"] == EVENT_TRANSACTION_CREATED
    assert state.attributes[ATTR_DATA] == TRANSACTION
    flex_state = hass.states.get("event.flex_transaction")
    assert flex_state is not None
    assert flex_state.state == "unknown"
    monzo.user_account.accounts.assert_awaited_once_with()
    monzo.user_account.pots.assert_awaited_once_with()


async def test_webhook_response_does_not_wait_for_refresh(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test slow polling does not delay the webhook response."""
    await setup_integration(hass, polling_config_entry)
    refresh_started = asyncio.Event()
    allow_refresh = asyncio.Event()
    refresh_finished = asyncio.Event()

    async def slow_accounts() -> list[dict]:
        refresh_started.set()
        await allow_refresh.wait()
        return []

    async def slow_pots() -> list[dict]:
        refresh_finished.set()
        return []

    monzo.user_account.accounts.side_effect = slow_accounts
    monzo.user_account.pots.side_effect = slow_pots
    client = await hass_client_no_auth()
    request_task = hass.async_create_task(
        client.post(
            async_generate_path(WEBHOOK_ID),
            json={"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: TRANSACTION},
        )
    )

    await refresh_started.wait()
    response = await asyncio.wait_for(request_task, 1)
    assert response.status == 200

    allow_refresh.set()
    await refresh_finished.wait()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([], id="not-a-dictionary"),
        pytest.param(
            {"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: []},
            id="data-not-a-dictionary",
        ),
        pytest.param(
            {"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: {}},
            id="missing-account-id",
        ),
        pytest.param(
            {
                "type": MONZO_WEBHOOK_TRANSACTION_CREATED,
                ATTR_DATA: {"account_id": "unknown"},
            },
            id="unknown-account",
        ),
        pytest.param(
            {"type": "unsupported.event", ATTR_DATA: TRANSACTION},
            id="unsupported-event",
        ),
    ],
)
async def test_invalid_webhook_is_ignored(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    payload: object,
) -> None:
    """Test invalid and unsupported webhooks do not trigger an entity."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.accounts.reset_mock()
    monzo.user_account.pots.reset_mock()
    client = await hass_client_no_auth()

    response = await client.post(async_generate_path(WEBHOOK_ID), json=payload)
    assert response.status == 200
    state = hass.states.get("event.current_account_transaction")
    assert state is not None
    assert state.state == "unknown"
    monzo.user_account.accounts.assert_not_awaited()
    monzo.user_account.pots.assert_not_awaited()


async def test_invalid_json_webhook_is_ignored(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test malformed JSON does not refresh Monzo data."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.accounts.reset_mock()
    monzo.user_account.pots.reset_mock()
    client = await hass_client_no_auth()

    response = await client.post(
        async_generate_path(WEBHOOK_ID),
        data="{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status == 200
    monzo.user_account.accounts.assert_not_awaited()
    monzo.user_account.pots.assert_not_awaited()


async def test_unload_preserves_remote_and_removes_local_webhooks(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test unloading preserves remote subscriptions and removes the handler."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.delete_webhook.reset_mock()
    monzo.user_account.accounts.reset_mock()
    monzo.user_account.pots.reset_mock()

    assert await hass.config_entries.async_unload(polling_config_entry.entry_id)

    monzo.user_account.delete_webhook.assert_not_awaited()
    client = await hass_client_no_auth()
    response = await client.post(
        async_generate_path(WEBHOOK_ID),
        json={"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: TRANSACTION},
    )
    assert response.status == 200
    monzo.user_account.accounts.assert_not_awaited()
    monzo.user_account.pots.assert_not_awaited()


async def test_uses_and_removes_cloudhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test a cloudhook is reused for remote subscriptions and entry removal."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [],
        [],
        [Webhook("webhook-acc_curr", "acc_curr", CLOUDHOOK_URL)],
        [Webhook("webhook-acc_flex", "acc_flex", CLOUDHOOK_URL)],
    ]
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as get_cloudhook,
        patch.object(cloud, "async_delete_cloudhook") as delete_cloudhook,
    ):
        await setup_integration(hass, polling_config_entry)

        get_cloudhook.assert_awaited_once_with(hass, WEBHOOK_ID)
        assert polling_config_entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL
        assert polling_config_entry.data[CONF_WEBHOOK_URL] == CLOUDHOOK_URL
        assert monzo.user_account.register_webhook.await_args_list == [
            call("acc_curr", CLOUDHOOK_URL),
            call("acc_flex", CLOUDHOOK_URL),
        ]

        await hass.config_entries.async_remove(polling_config_entry.entry_id)

    delete_cloudhook.assert_awaited_once_with(hass, WEBHOOK_ID)
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("webhook-acc_curr"),
        call("webhook-acc_flex"),
    ]


async def test_removal_refreshes_expired_token_without_updating_entry(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test removal can refresh a token after the entry has been deleted."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [],
        [],
        [Webhook("webhook-acc_curr", "acc_curr", WEBHOOK_URL)],
        [Webhook("webhook-acc_flex", "acc_flex", WEBHOOK_URL)],
    ]
    await setup_integration(hass, polling_config_entry)
    expired_token = {**polling_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        polling_config_entry,
        data={**polling_config_entry.data, "token": expired_token},
    )
    implementation = await async_get_config_entry_implementation(
        hass, polling_config_entry
    )
    refreshed_token = {**expired_token, "access_token": "refreshed-access-token"}

    with (
        patch.object(
            implementation,
            "async_refresh_token",
            return_value=refreshed_token,
        ) as refresh_token,
        patch(
            "homeassistant.components.monzo.async_get_config_entry_implementation",
            return_value=implementation,
        ),
    ):
        await hass.config_entries.async_remove(polling_config_entry.entry_id)

    refresh_token.assert_awaited_once_with(expired_token)
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("webhook-acc_curr"),
        call("webhook-acc_flex"),
    ]


async def test_remote_cleanup_failure_still_removes_cloudhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test remote cleanup failure does not prevent cloudhook removal."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
        patch.object(cloud, "async_delete_cloudhook") as delete_cloudhook,
    ):
        await setup_integration(hass, polling_config_entry)
        monzo.user_account.accounts.side_effect = AuthorisationExpiredError

        await hass.config_entries.async_remove(polling_config_entry.entry_id)

    delete_cloudhook.assert_awaited_once_with(hass, WEBHOOK_ID)


async def test_uses_external_url_until_cloud_connects(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test registration moves from the external URL when cloud connects."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=False),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as get_cloudhook,
    ):
        await setup_integration(hass, polling_config_entry)
        get_cloudhook.assert_not_awaited()
        assert monzo.user_account.register_webhook.await_args_list == [
            call("acc_curr", WEBHOOK_URL),
            call("acc_flex", WEBHOOK_URL),
        ]

        with patch.object(cloud, "async_is_connected", return_value=True):
            async_mock_cloud_connection_status(hass, True)
            await hass.async_block_till_done()

    get_cloudhook.assert_awaited_once_with(hass, WEBHOOK_ID)
    assert monzo.user_account.register_webhook.await_args_list[-2:] == [
        call("acc_curr", CLOUDHOOK_URL),
        call("acc_flex", CLOUDHOOK_URL),
    ]


async def test_temporary_cloud_disconnect_preserves_cloudhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test a temporary Cloud disconnect preserves its remote callback."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
    ):
        await setup_integration(hass, polling_config_entry)
        monzo.user_account.list_account_webhooks.reset_mock()

        async_mock_cloud_connection_status(hass, False)
        await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_WEBHOOK_URL] == CLOUDHOOK_URL
    monzo.user_account.list_account_webhooks.assert_not_awaited()


async def test_cloud_subscription_loss_falls_back_to_external_url(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test losing a Cloud subscription replaces its remote callback."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
    ):
        await setup_integration(hass, polling_config_entry)
        assert polling_config_entry.runtime_data.webhook_manager.diagnostics_data[
            "uses_cloudhook"
        ]
        monzo.user_account.list_account_webhooks.side_effect = [
            [Webhook("old-current", "acc_curr", CLOUDHOOK_URL)],
            [Webhook("old-flex", "acc_flex", CLOUDHOOK_URL)],
        ]
        monzo.user_account.register_webhook.reset_mock()
        monzo.user_account.delete_webhook.reset_mock()

        with patch.object(cloud, "async_active_subscription", return_value=False):
            async_mock_cloud_connection_status(hass, False)
            await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL
    assert polling_config_entry.data[CONF_WEBHOOK_URL] == WEBHOOK_URL
    assert not polling_config_entry.runtime_data.webhook_manager.diagnostics_data[
        "uses_cloudhook"
    ]
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", WEBHOOK_URL),
        call("acc_flex", WEBHOOK_URL),
    ]


async def test_cloudhook_change_is_persisted_and_reconciled(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test a changed cloudhook replaces the persisted remote callback."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
        patch.object(cloud, "async_listen_cloudhook_change") as listen_cloudhook,
    ):
        await setup_integration(hass, polling_config_entry)
        cloudhook_changed = listen_cloudhook.call_args.args[2]
        monzo.user_account.list_account_webhooks.reset_mock()
        cloudhook_changed({"cloudhook_url": CLOUDHOOK_URL})
        await hass.async_block_till_done()
        monzo.user_account.list_account_webhooks.assert_not_awaited()

        monzo.user_account.list_account_webhooks.side_effect = [
            [Webhook("old-current", "acc_curr", CLOUDHOOK_URL)],
            [Webhook("old-flex", "acc_flex", CLOUDHOOK_URL)],
        ]
        monzo.user_account.register_webhook.reset_mock()

        cloudhook_changed({"cloudhook_url": NEW_CLOUDHOOK_URL})
        await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_CLOUDHOOK_URL] == NEW_CLOUDHOOK_URL
    assert polling_config_entry.data[CONF_WEBHOOK_URL] == NEW_CLOUDHOOK_URL
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", NEW_CLOUDHOOK_URL),
        call("acc_flex", NEW_CLOUDHOOK_URL),
    ]


async def test_removed_cloudhook_falls_back_to_external_url(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test deleting a cloudhook moves remote callbacks to the external URL."""
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
        patch.object(cloud, "async_listen_cloudhook_change") as listen_cloudhook,
    ):
        await setup_integration(hass, polling_config_entry)
        monzo.user_account.list_account_webhooks.side_effect = [
            [Webhook("old-current", "acc_curr", CLOUDHOOK_URL)],
            [Webhook("old-flex", "acc_flex", CLOUDHOOK_URL)],
        ]
        monzo.user_account.register_webhook.reset_mock()

        with patch.object(cloud, "async_active_subscription", return_value=False):
            listen_cloudhook.call_args.args[2](None)
            await hass.async_block_till_done()

    assert CONF_CLOUDHOOK_URL not in polling_config_entry.data
    assert polling_config_entry.data[CONF_WEBHOOK_URL] == WEBHOOK_URL
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", WEBHOOK_URL),
        call("acc_flex", WEBHOOK_URL),
    ]


async def test_external_url_change_is_reconciled(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test changing the external URL replaces remote callbacks."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.list_account_webhooks.reset_mock()
    await hass.config.async_update(currency="USD")
    await hass.async_block_till_done()
    monzo.user_account.list_account_webhooks.assert_not_awaited()

    monzo.user_account.list_account_webhooks.side_effect = [
        [Webhook("old-current", "acc_curr", WEBHOOK_URL)],
        [Webhook("old-flex", "acc_flex", WEBHOOK_URL)],
    ]
    monzo.user_account.register_webhook.reset_mock()

    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        return_value=NEW_WEBHOOK_URL,
    ):
        await hass.config.async_update(external_url="https://new.example.com")
        await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_WEBHOOK_URL] == NEW_WEBHOOK_URL
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]
    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", NEW_WEBHOOK_URL),
        call("acc_flex", NEW_WEBHOOK_URL),
    ]


async def test_external_url_removal_cleans_up_remote_webhooks(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test removing the external URL removes obsolete remote callbacks."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.list_account_webhooks.side_effect = [
        [Webhook("old-current", "acc_curr", WEBHOOK_URL)],
        [Webhook("old-flex", "acc_flex", WEBHOOK_URL)],
    ]
    monzo.user_account.delete_webhook.reset_mock()

    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        side_effect=NoURLAvailableError,
    ):
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()

    assert CONF_WEBHOOK_URL not in polling_config_entry.data
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]


async def test_external_url_cleanup_auth_failure_starts_reauthentication(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test obsolete webhook cleanup authenticates before discarding its URL."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.list_account_webhooks.side_effect = AuthorisationExpiredError

    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        side_effect=NoURLAvailableError,
    ):
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_WEBHOOK_URL] == WEBHOOK_URL
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_external_url_cleanup_oauth_failure_starts_reauthentication(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token refresh starts reauthentication during cleanup."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.list_account_webhooks.reset_mock()
    monzo.user_account.list_account_webhooks.side_effect = (
        OAuth2TokenRequestReauthError(request_info=Mock(), domain="monzo")
    )

    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        side_effect=NoURLAvailableError,
    ):
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert polling_config_entry.data[CONF_WEBHOOK_URL] == WEBHOOK_URL
    monzo.user_account.list_account_webhooks.assert_awaited_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_external_url_cleanup_failure_is_retried_once(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test repeated URL updates share one remote cleanup retry."""
    caplog.set_level(logging.INFO)
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.list_account_webhooks.side_effect = [
        InvalidMonzoAPIResponseError(),
        InvalidMonzoAPIResponseError(),
        [Webhook("old-current", "acc_curr", WEBHOOK_URL)],
        [Webhook("old-flex", "acc_flex", WEBHOOK_URL)],
    ]
    monzo.user_account.delete_webhook.reset_mock()

    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        side_effect=NoURLAvailableError,
    ):
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert CONF_WEBHOOK_URL not in polling_config_entry.data
    assert monzo.user_account.delete_webhook.await_args_list == [
        call("old-current"),
        call("old-flex"),
    ]
    assert caplog.text.count("Unable to remove obsolete Monzo webhooks") == 1
    assert caplog.text.count("Successfully updated Monzo webhooks after retrying") == 1


async def test_no_external_url_skips_remote_registration(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test setup continues without remote registration when no URL exists."""
    with patch(
        "homeassistant.components.monzo.webhook.webhook.async_generate_url",
        side_effect=NoURLAvailableError,
    ):
        await setup_integration(hass, polling_config_entry)

    monzo.user_account.list_account_webhooks.assert_not_awaited()
    monzo.user_account.register_webhook.assert_not_awaited()


async def test_cloudhook_creation_failure_is_retried(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unavailable cloud connection schedules webhook registration retry."""
    caplog.set_level(logging.INFO)
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            side_effect=[cloud.CloudNotAvailable, CLOUDHOOK_URL],
        ),
    ):
        await setup_integration(hass, polling_config_entry)
        monzo.user_account.register_webhook.assert_not_awaited()

        freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert monzo.user_account.register_webhook.await_args_list == [
        call("acc_curr", CLOUDHOOK_URL),
        call("acc_flex", CLOUDHOOK_URL),
    ]
    assert "Unable to create Monzo cloud webhook; retrying in 60 seconds" in caplog.text
    assert "Successfully updated Monzo webhooks after retrying" in caplog.text


async def test_retry_is_cancelled_when_callback_url_becomes_unavailable(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a retry is cancelled when there is no callback or previous URL."""
    caplog.set_level(logging.INFO)
    with (
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(
            cloud,
            "async_get_or_create_cloudhook",
            side_effect=cloud.CloudNotAvailable,
        ),
    ):
        await setup_integration(hass, polling_config_entry)

    with (
        patch.object(cloud, "async_active_subscription", return_value=False),
        patch(
            "homeassistant.components.monzo.webhook.webhook.async_generate_url",
            side_effect=NoURLAvailableError,
        ) as generate_url,
    ):
        await hass.config.async_update(external_url=None)
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    generate_url.assert_called_once()
    monzo.user_account.list_account_webhooks.assert_not_awaited()
    assert "Successfully updated Monzo webhooks after retrying" not in caplog.text


async def test_registration_auth_failure_starts_reauthentication(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test an expired token starts config entry reauthentication."""
    monzo.user_account.list_account_webhooks.side_effect = AuthorisationExpiredError

    await setup_integration(hass, polling_config_entry)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_registration_oauth_failure_starts_reauthentication(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token refresh starts reauthentication during registration."""
    monzo.user_account.list_account_webhooks.side_effect = [
        [],
        OAuth2TokenRequestReauthError(request_info=Mock(), domain="monzo"),
    ]

    await setup_integration(hass, polling_config_entry)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert monzo.user_account.list_account_webhooks.await_count == 2
    monzo.user_account.delete_webhook.assert_awaited_once_with("webhook-acc_curr")
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_registration_failure_is_retried(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a transient invalid response schedules another registration attempt."""
    caplog.set_level(logging.INFO)
    monzo.user_account.list_account_webhooks.side_effect = [
        InvalidMonzoAPIResponseError(),
        InvalidMonzoAPIResponseError(),
        [],
        [],
    ]

    await setup_integration(hass, polling_config_entry)
    assert monzo.user_account.register_webhook.await_count == 0

    freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert monzo.user_account.register_webhook.await_count == 2
    assert caplog.text.count("Unable to register Monzo webhooks") == 1
    assert caplog.text.count("Successfully updated Monzo webhooks after retrying") == 1
