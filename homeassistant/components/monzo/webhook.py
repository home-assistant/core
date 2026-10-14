"""Webhook support for the Monzo integration."""

import asyncio
from collections.abc import Iterable, Mapping
from datetime import datetime
import logging
from typing import Any

from aiohttp import ClientError
from aiohttp.hdrs import METH_POST
from aiohttp.web import Request
from monzopy import (
    AbstractMonzoApi,
    AuthorisationExpiredError,
    InvalidMonzoAPIResponseError,
)

from homeassistant.components import cloud, webhook
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import NoURLAvailableError

from .const import (
    ATTR_DATA,
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_URL,
    DOMAIN,
    EVENT_TRANSACTION_CREATED,
    MONZO_WEBHOOK_TRANSACTION_CREATED,
)
from .coordinator import MonzoConfigEntry, MonzoCoordinator

_LOGGER = logging.getLogger(__name__)

WEBHOOK_RETRY_DELAY = 60


def webhook_signal(account_id: str) -> str:
    """Return the dispatcher signal for a Monzo account."""
    return f"{DOMAIN}_webhook_{account_id}"


async def async_delete_remote_webhooks(
    api: AbstractMonzoApi, account_ids: Iterable[str], webhook_url: str
) -> None:
    """Delete remote Monzo webhooks registered to a Home Assistant URL."""
    for account_id in account_ids:
        account_webhooks = await api.user_account.list_account_webhooks(account_id)
        for account_webhook in account_webhooks:
            if account_webhook.url == webhook_url:
                await api.user_account.delete_webhook(account_webhook.id)


class MonzoWebhookManager:
    """Manage Home Assistant and Monzo webhooks for a config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MonzoConfigEntry,
        coordinator: MonzoCoordinator,
    ) -> None:
        """Initialize the webhook manager."""
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._active = True
        self._register_lock = asyncio.Lock()
        self._retry_cancel: CALLBACK_TYPE | None = None
        self._retrying = False
        self._webhook_url: str | None = None
        self._known_account_ids: set[str] = set()

    @property
    def diagnostics_data(self) -> dict[str, bool | int]:
        """Return privacy-safe webhook diagnostics."""
        return {
            "active": self._active,
            "has_registered_webhook_url": self._webhook_url is not None,
            "known_account_count": len(self._known_account_ids),
            "retry_scheduled": self._retry_cancel is not None,
            "retrying": self._retrying,
            "uses_cloudhook": self._webhook_url is not None
            and self._webhook_url == self.entry.data.get(CONF_CLOUDHOOK_URL),
        }

    async def async_setup(self) -> None:
        """Set up the local webhook and remote subscriptions."""
        webhook.async_register(
            self.hass,
            DOMAIN,
            self.entry.title,
            self.entry.data[CONF_WEBHOOK_ID],
            self.async_handle_webhook,
            allowed_methods=[METH_POST],
        )
        self.entry.async_on_unload(self._async_unregister_local_webhook)
        self.entry.async_on_unload(self._cancel_retry)
        self.entry.async_on_unload(
            cloud.async_listen_connection_change(
                self.hass, self._async_cloud_connection_changed
            )
        )
        self.entry.async_on_unload(
            cloud.async_listen_cloudhook_change(
                self.hass,
                self.entry.data[CONF_WEBHOOK_ID],
                self._async_cloudhook_changed,
            )
        )
        self.entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._async_core_config_updated
            )
        )
        self._known_account_ids.update(self.coordinator.data.accounts)
        self.entry.async_on_unload(
            self.coordinator.async_add_listener(self._async_accounts_updated)
        )
        await self.async_register_remote_webhooks()

    async def async_register_remote_webhooks(
        self, _now: datetime | None = None
    ) -> None:
        """Reconcile remote Monzo webhooks for every account."""
        async with self._register_lock:
            if not self._active:
                return

            webhook_url: str | None = None
            if cloud.async_active_subscription(self.hass):
                webhook_url = self.entry.data.get(CONF_CLOUDHOOK_URL)
                if webhook_url is None and cloud.async_is_connected(self.hass):
                    try:
                        webhook_url = await cloud.async_get_or_create_cloudhook(
                            self.hass, self.entry.data[CONF_WEBHOOK_ID]
                        )
                    except cloud.CloudNotAvailable:
                        self._schedule_retry("Unable to create Monzo cloud webhook")
                        return
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={**self.entry.data, CONF_CLOUDHOOK_URL: webhook_url},
                    )

            if not webhook_url:
                try:
                    webhook_url = webhook.async_generate_url(
                        self.hass,
                        self.entry.data[CONF_WEBHOOK_ID],
                        allow_internal=False,
                    )
                except NoURLAvailableError:
                    _LOGGER.warning(
                        "Monzo webhooks require an external Home Assistant URL"
                    )
                    await self._async_remove_previous_remote_webhooks()
                    return

            registered_webhook_ids: list[str] = []
            try:
                await self._async_reconcile_remote_webhooks(
                    webhook_url, registered_webhook_ids
                )
            except AuthorisationExpiredError, OAuth2TokenRequestReauthError:
                await self._async_rollback_remote_webhooks(registered_webhook_ids)
                self.entry.async_start_reauth(self.hass)
                return
            except (ClientError, InvalidMonzoAPIResponseError, TimeoutError) as err:
                await self._async_rollback_remote_webhooks(registered_webhook_ids)
                self._schedule_retry("Unable to register Monzo webhooks", err)
                return

            self._cancel_retry()
            self._log_retry_success()
            self._webhook_url = webhook_url
            if self.entry.data.get(CONF_WEBHOOK_URL) != webhook_url:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, CONF_WEBHOOK_URL: webhook_url},
                )

    async def _async_reconcile_remote_webhooks(
        self, webhook_url: str, registered_webhook_ids: list[str]
    ) -> None:
        """Ensure each account has exactly one webhook using our URL."""
        previous_url = self.entry.data.get(CONF_WEBHOOK_URL)

        for account_id in self.coordinator.data.accounts:
            account_webhooks = (
                await self.coordinator.api.user_account.list_account_webhooks(
                    account_id
                )
            )

            matching_webhooks = []
            for account_webhook in account_webhooks:
                if previous_url and account_webhook.url == previous_url:
                    if previous_url != webhook_url:
                        await self.coordinator.api.user_account.delete_webhook(
                            account_webhook.id
                        )
                    else:
                        matching_webhooks.append(account_webhook)
                elif account_webhook.url == webhook_url:
                    matching_webhooks.append(account_webhook)

            if matching_webhooks:
                for duplicate in matching_webhooks[1:]:
                    await self.coordinator.api.user_account.delete_webhook(duplicate.id)
            else:
                registered = await self.coordinator.api.user_account.register_webhook(
                    account_id, webhook_url
                )
                registered_webhook_ids.append(registered.id)

    async def _async_rollback_remote_webhooks(self, webhook_ids: list[str]) -> None:
        """Roll back webhooks created during an incomplete reconciliation."""
        for webhook_id in webhook_ids:
            try:
                await self.coordinator.api.user_account.delete_webhook(webhook_id)
            except (
                AuthorisationExpiredError,
                ClientError,
                InvalidMonzoAPIResponseError,
                TimeoutError,
            ) as err:
                _LOGGER.warning(
                    "Unable to roll back Monzo webhook %s: %s", webhook_id, err
                )

    async def _async_remove_previous_remote_webhooks(self) -> None:
        """Remove remote webhooks when no callback URL is available."""
        if (previous_url := self.entry.data.get(CONF_WEBHOOK_URL)) is None:
            self._cancel_retry()
            self._retrying = False
            return

        try:
            await async_delete_remote_webhooks(
                self.coordinator.api,
                self.coordinator.data.accounts,
                previous_url,
            )
        except AuthorisationExpiredError, OAuth2TokenRequestReauthError:
            self.entry.async_start_reauth(self.hass)
            return
        except (ClientError, InvalidMonzoAPIResponseError, TimeoutError) as err:
            self._schedule_retry("Unable to remove obsolete Monzo webhooks", err)
            return

        self._cancel_retry()
        self._log_retry_success()
        self._webhook_url = None
        data = dict(self.entry.data)
        data.pop(CONF_WEBHOOK_URL, None)
        self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def async_unload(self) -> None:
        """Unload the webhook manager while preserving remote subscriptions."""
        self._active = False
        self._cancel_retry()

        async with self._register_lock:
            self._async_unregister_local_webhook()

    async def async_handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Handle an incoming Monzo webhook."""
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.warning("Received invalid JSON from a Monzo webhook")
            return

        if not isinstance(payload, Mapping):
            _LOGGER.warning("Received an invalid Monzo webhook payload")
            return

        event_type = payload.get("type")
        if event_type != MONZO_WEBHOOK_TRANSACTION_CREATED:
            _LOGGER.debug("Ignoring unsupported Monzo webhook type %s", event_type)
            return

        transaction = payload.get(ATTR_DATA)
        if not isinstance(transaction, dict) or not isinstance(
            account_id := transaction.get("account_id"), str
        ):
            _LOGGER.warning("Received an invalid Monzo transaction webhook")
            return

        if account_id not in self.coordinator.data.accounts:
            _LOGGER.warning("Received a Monzo webhook for an unknown account")
            return

        async_dispatcher_send(
            hass,
            webhook_signal(account_id),
            EVENT_TRANSACTION_CREATED,
            transaction,
        )
        self.entry.async_create_background_task(
            self.hass,
            self.coordinator.async_request_refresh(),
            "refresh Monzo data",
        )

    @callback
    def _async_cloud_connection_changed(
        self, state: cloud.CloudConnectionState
    ) -> None:
        """Reconcile webhooks when Home Assistant Cloud availability changes."""
        if (
            state is cloud.CloudConnectionState.CLOUD_DISCONNECTED
            and cloud.async_active_subscription(self.hass)
        ):
            return
        self._async_schedule_registration("update Monzo webhooks")

    @callback
    def _async_cloudhook_changed(self, cloudhook: dict[str, Any] | None) -> None:
        """Reconcile remote webhooks when our cloudhook changes."""
        cloudhook_url = cloudhook.get("cloudhook_url") if cloudhook else None
        data = dict(self.entry.data)
        if cloudhook_url is None:
            data.pop(CONF_CLOUDHOOK_URL, None)
        else:
            data[CONF_CLOUDHOOK_URL] = cloudhook_url
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        if self._webhook_url == cloudhook_url:
            return
        self._async_schedule_registration("update Monzo webhooks")

    @callback
    def _async_core_config_updated(self, event: Event[dict[str, Any]]) -> None:
        """Reconcile remote webhooks when the external URL changes."""
        if "external_url" not in event.data:
            return
        self._async_schedule_registration("update Monzo webhooks")

    @callback
    def _async_accounts_updated(self) -> None:
        """Reconcile webhooks when the set of Monzo accounts changes."""
        current_account_ids = set(self.coordinator.data.accounts)
        new_account_ids = current_account_ids - self._known_account_ids
        self._known_account_ids = current_account_ids
        if new_account_ids:
            self._async_schedule_registration("add webhooks for new Monzo accounts")

    @callback
    def _async_schedule_registration(self, name: str) -> None:
        """Schedule remote webhook reconciliation."""
        self.entry.async_create_task(
            self.hass,
            self.async_register_remote_webhooks(),
            name,
        )

    def _schedule_retry(self, message: str, err: Exception | None = None) -> None:
        """Schedule another remote webhook registration attempt."""
        if self._retry_cancel is not None:
            return
        if not self._retrying:
            if err is None:
                _LOGGER.info("%s; retrying in %s seconds", message, WEBHOOK_RETRY_DELAY)
            else:
                _LOGGER.info(
                    "%s: %s; retrying in %s seconds",
                    message,
                    err,
                    WEBHOOK_RETRY_DELAY,
                )
            self._retrying = True
        self._retry_cancel = async_call_later(
            self.hass, WEBHOOK_RETRY_DELAY, self._async_retry
        )

    def _log_retry_success(self) -> None:
        """Log when remote webhook management recovers."""
        if self._retrying:
            _LOGGER.info("Successfully updated Monzo webhooks after retrying")
            self._retrying = False

    async def _async_retry(self, now: datetime) -> None:
        """Retry remote webhook registration."""
        self._retry_cancel = None
        await self.async_register_remote_webhooks(now)

    def _cancel_retry(self) -> None:
        """Cancel a pending registration retry."""
        if self._retry_cancel is not None:
            self._retry_cancel()
            self._retry_cancel = None

    @callback
    def _async_unregister_local_webhook(self) -> None:
        """Unregister the local Home Assistant webhook."""
        webhook.async_unregister(self.hass, self.entry.data[CONF_WEBHOOK_ID])
