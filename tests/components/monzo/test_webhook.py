"""Tests for Monzo webhooks and transaction event entities."""

from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError, Webhook
import pytest

from homeassistant.components import cloud
from homeassistant.components.monzo.const import (
    ATTR_DATA,
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_URL,
    EVENT_TRANSACTION_CREATED,
    MONZO_WEBHOOK_TRANSACTION_CREATED,
)
from homeassistant.components.monzo.webhook import WEBHOOK_RETRY_DELAY
from homeassistant.components.webhook import async_generate_path
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import WEBHOOK_ID, WEBHOOK_URL

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_cloud_connection_status,
)
from tests.typing import ClientSessionGenerator

CLOUDHOOK_URL = "https://hooks.nabu.casa/test-cloudhook"
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


async def test_unload_removes_owned_remote_and_local_webhooks(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test unloading cleans up only the subscriptions owned by the entry."""
    await setup_integration(hass, polling_config_entry)
    monzo.user_account.delete_webhook.reset_mock()

    assert await hass.config_entries.async_unload(polling_config_entry.entry_id)

    assert {
        item.args[0] for item in monzo.user_account.delete_webhook.await_args_list
    } == {
        "webhook-acc_curr",
        "webhook-acc_flex",
    }
    client = await hass_client_no_auth()
    response = await client.post(
        async_generate_path(WEBHOOK_ID),
        json={"type": MONZO_WEBHOOK_TRANSACTION_CREATED, ATTR_DATA: TRANSACTION},
    )
    assert response.status == 200


async def test_uses_and_removes_cloudhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test a cloudhook is reused for remote subscriptions and entry removal."""
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


async def test_registration_failure_is_retried(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a transient invalid response schedules another registration attempt."""
    monzo.user_account.list_account_webhooks.side_effect = [
        InvalidMonzoAPIResponseError(),
        [],
        [],
    ]

    await setup_integration(hass, polling_config_entry)
    assert monzo.user_account.register_webhook.await_count == 0

    freezer.tick(timedelta(seconds=WEBHOOK_RETRY_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert monzo.user_account.register_webhook.await_count == 2
