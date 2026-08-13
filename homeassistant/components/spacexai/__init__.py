"""The SpaceXAI integration."""

from dataclasses import dataclass
from typing import cast

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import entity_platform, issue_registry as ir
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    LocalOAuth2Implementation,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.json import json_dumps

from .client import (
    OAuthAccessTokenProvider,
    ProviderSnapshot,
    SpaceXAIClient,
    StaticAccessTokenProvider,
)
from .const import DEFAULT_MODEL_PLACEHOLDER, DOMAIN, ISSUE_MODEL_NOT_ENTITLED, LOGGER
from .errors import (
    AccountMismatchError,
    AuthenticationRejectedError,
    ConnectionFailureError,
    ErrorContext,
    ModelNotEntitledError,
    NoConversationModelsError,
    Operation,
    PermanentProviderError,
    QuotaLimitedError,
    RateLimitedError,
    ReauthenticationRequiredError,
    RefreshRejectedError,
    RequestTimeoutError,
    SpaceXAIError,
    SubscriptionNotEntitledError,
    TransientProviderError,
)
from .issue import (
    async_create_model_not_entitled_issue,
    async_create_subscription_issue,
    async_delete_model_not_entitled_issue,
    async_delete_subscription_issue,
)

PLATFORMS = (Platform.CONVERSATION,)


@dataclass(slots=True)
class SpaceXAIData:
    """Runtime data for one SpaceXAI account."""

    client: SpaceXAIClient
    snapshot: ProviderSnapshot
    subentries: tuple[tuple[str, str, str], ...]


type SpaceXAIConfigEntry = ConfigEntry[SpaceXAIData]


async def async_setup_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> bool:
    """Set up SpaceXAI from a config entry."""
    if _async_update_entry not in entry.update_listeners:
        entry.add_update_listener(_async_update_entry)
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except (ImplementationUnavailableError, ValueError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth_implementation_unavailable",
        ) from err

    client = SpaceXAIClient(
        hass,
        OAuthAccessTokenProvider(OAuth2Session(hass, entry, implementation)),
        runtime_session=True,
    )
    try:
        snapshot = await client.async_validate(expected_subject=entry.unique_id)
    except AccountMismatchError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="account_mismatch",
        ) from err
    except (
        AuthenticationRejectedError,
        ReauthenticationRequiredError,
        RefreshRejectedError,
    ) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="reauthentication_required",
        ) from err
    except (
        ConnectionFailureError,
        RateLimitedError,
        RequestTimeoutError,
        TransientProviderError,
    ) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="provider_unavailable",
        ) from err
    except SubscriptionNotEntitledError as err:
        async_create_subscription_issue(hass, entry)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="subscription_not_entitled",
        ) from err
    except NoConversationModelsError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_conversation_models",
        ) from err
    except QuotaLimitedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="quota_limited",
            translation_placeholders={"model": DEFAULT_MODEL_PLACEHOLDER},
        ) from err
    except ModelNotEntitledError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="model_not_entitled",
            translation_placeholders={
                "model": err.context.model or DEFAULT_MODEL_PLACEHOLDER
            },
        ) from err
    except PermanentProviderError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="permanent_provider_failure",
            translation_placeholders={
                "model": err.context.model or DEFAULT_MODEL_PLACEHOLDER
            },
        ) from err
    except SpaceXAIError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="malformed_provider_response",
            translation_placeholders={"model": DEFAULT_MODEL_PLACEHOLDER},
        ) from err

    entry.runtime_data = SpaceXAIData(
        client=client,
        snapshot=snapshot,
        subentries=_subentry_fingerprint(entry),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_clear_orphaned_model_repairs(hass, entry)
    async_reconcile_snapshot(hass, entry, snapshot)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> bool:
    """Unload a SpaceXAI config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> None:
    """Revoke the OAuth refresh token when an entry is removed."""
    async_delete_subscription_issue(hass, entry.entry_id)
    async_clear_orphaned_model_repairs(hass, entry, include_current=True)

    token = entry.data.get("token")
    if not isinstance(token, dict) or not isinstance(
        refresh_token := token.get("refresh_token"), str
    ):
        LOGGER.warning(
            "Unable to revoke SpaceXAI OAuth token: reason=missing_refresh_token"
        )
        return

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError, ValueError:
        LOGGER.warning(
            "Unable to revoke SpaceXAI OAuth token: reason=implementation_unavailable"
        )
        return
    if not isinstance(implementation, LocalOAuth2Implementation):
        LOGGER.warning(
            "Unable to revoke SpaceXAI OAuth token: reason=foreign_implementation"
        )
        return

    client = SpaceXAIClient(
        hass,
        StaticAccessTokenProvider(""),
        runtime_session=False,
    )
    try:
        await client.async_revoke(
            refresh_token,
            implementation.client_id,
            implementation.client_secret,
        )
    except SpaceXAIError as err:
        LOGGER.warning(
            "Unable to revoke SpaceXAI OAuth token: category=%s operation=%s "
            "status=%s request_id=%s retryable=%s",
            err.category,
            err.context.operation,
            err.context.status,
            err.context.request_id,
            err.retryable,
        )


@callback
def async_mark_subscription_not_entitled(
    hass: HomeAssistant,
    entry: SpaceXAIConfigEntry,
    *,
    operation: Operation = Operation.MODELS,
) -> None:
    """Create the subscription repair and mark loaded conversation entities down."""
    async_create_subscription_issue(hass, entry)
    err = SubscriptionNotEntitledError(
        "Account is not entitled for subscription-backed Grok access",
        context=ErrorContext(operation=operation),
    )
    for platform in entity_platform.async_get_platforms(hass, DOMAIN):
        for entity in platform.entities.values():
            if getattr(entity, "entry", None) is not entry:
                continue
            mark = getattr(entity, "_mark_unavailable", None)
            if mark is None:
                continue
            mark(err, account_wide=True)


@callback
def async_reconcile_snapshot(
    hass: HomeAssistant,
    entry: SpaceXAIConfigEntry,
    snapshot: ProviderSnapshot,
) -> None:
    """Apply a fresh snapshot to repairs and loaded conversation entities."""
    entry.runtime_data.snapshot = snapshot
    async_delete_subscription_issue(hass, entry.entry_id)
    for subentry in entry.subentries.values():
        if CONF_MODEL not in subentry.data:
            continue
        model = cast(str, subentry.data[CONF_MODEL])
        if snapshot.has_model(model):
            async_delete_model_not_entitled_issue(hass, subentry.subentry_id)
        else:
            async_create_model_not_entitled_issue(
                hass,
                entry,
                subentry_id=subentry.subentry_id,
                model=model,
            )

    for platform in entity_platform.async_get_platforms(hass, DOMAIN):
        for entity in platform.entities.values():
            apply = getattr(entity, "async_apply_model_entitlement", None)
            if apply is None or getattr(entity, "entry", None) is not entry:
                continue
            apply()


def _subentry_fingerprint(
    entry: SpaceXAIConfigEntry,
) -> tuple[tuple[str, str, str], ...]:
    """Return the stored subentry configuration fingerprint."""
    return tuple(
        sorted(
            (
                subentry.subentry_id,
                subentry.title,
                json_dumps(dict(subentry.data)),
            )
            for subentry in entry.subentries.values()
        )
    )


@callback
def async_clear_orphaned_model_repairs(
    hass: HomeAssistant,
    entry: SpaceXAIConfigEntry,
    *,
    include_current: bool = False,
) -> None:
    """Delete model repairs whose subentry is no longer on this entry."""
    current_ids: set[str] = set() if include_current else set(entry.subentries)
    for issue in list(ir.async_get(hass).issues.values()):
        if issue.domain != DOMAIN or not issue.issue_id.startswith(
            f"{ISSUE_MODEL_NOT_ENTITLED}_"
        ):
            continue
        data = issue.data or {}
        if data.get("entry_id") != entry.entry_id:
            continue
        if data.get("subentry_id") in current_ids:
            continue
        ir.async_delete_issue(hass, DOMAIN, issue.issue_id)


async def _async_update_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> None:
    """Clear removed-subentry repairs and reload when loaded config changes."""
    async_clear_orphaned_model_repairs(hass, entry)
    if entry.state is not ConfigEntryState.LOADED:
        return
    if _subentry_fingerprint(entry) == entry.runtime_data.subentries:
        return
    await hass.config_entries.async_reload(entry.entry_id)
