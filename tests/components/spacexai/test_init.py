"""Tests for SpaceXAI setup and lifecycle."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.spacexai import (
    async_reconcile_snapshot,
    async_remove_entry,
)
from homeassistant.components.spacexai.client import (
    AccountInfo,
    ModelInfo,
    ProviderSnapshot,
)
from homeassistant.components.spacexai.const import (
    CONF_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DOMAIN,
)
from homeassistant.components.spacexai.errors import (
    AccountMismatchError,
    AuthenticationRejectedError,
    ConnectionFailureError,
    ErrorContext,
    MalformedProviderResponseError,
    ModelNotEntitledError,
    NoConversationModelsError,
    Operation,
    PermanentProviderError,
    QuotaLimitedError,
    RateLimitedError,
    ReauthenticationRequiredError,
    RefreshRejectedError,
    RequestTimeoutError,
    SubscriptionNotEntitledError,
    TransientProviderError,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir, llm
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import AGENT_ID, conversation_subentry
from .conftest import ACCESS_TOKEN, ACCOUNT_ID, REFRESH_TOKEN

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_credentials", "mock_validate")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up and unload the Conversation platform."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(AGENT_ID) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_credentials")
async def test_oauth_token_update_does_not_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
) -> None:
    """Do not reload entities for normal OAuth refresh-token rotation."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "token": {
                **mock_config_entry.data["token"],
                "access_token": "rotated-access-token",
                "refresh_token": "rotated-refresh-token",
            },
        },
    )
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_validate.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            ReauthenticationRequiredError(
                "expired",
                context=ErrorContext(operation=Operation.ACCOUNT),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="reauthentication",
        ),
        pytest.param(
            AuthenticationRejectedError(
                "rejected",
                context=ErrorContext(operation=Operation.ACCOUNT),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="authentication_rejected",
        ),
        pytest.param(
            RefreshRejectedError(
                "refresh rejected",
                context=ErrorContext(operation=Operation.REFRESH),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="refresh_rejected",
        ),
        pytest.param(
            ConnectionFailureError(
                "offline",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_RETRY,
            id="connection",
        ),
        pytest.param(
            RateLimitedError(
                "limited",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_RETRY,
            id="rate_limited",
        ),
        pytest.param(
            RequestTimeoutError(
                "timeout",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_RETRY,
            id="timeout",
        ),
        pytest.param(
            TransientProviderError(
                "transient",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_RETRY,
            id="transient",
        ),
        pytest.param(
            SubscriptionNotEntitledError(
                "not entitled",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="subscription",
        ),
        pytest.param(
            NoConversationModelsError(
                "none",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="no-models",
        ),
        pytest.param(
            QuotaLimitedError(
                "quota",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="quota",
        ),
        pytest.param(
            PermanentProviderError(
                "denied",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="permanent",
        ),
        pytest.param(
            ModelNotEntitledError(
                "model",
                context=ErrorContext(operation=Operation.MODELS),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="model",
        ),
        pytest.param(
            MalformedProviderResponseError(
                "malformed",
                context=ErrorContext(operation=Operation.ACCOUNT),
            ),
            ConfigEntryState.SETUP_ERROR,
            id="malformed",
        ),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Map provider failures into config-entry setup behavior."""
    mock_validate.side_effect = side_effect
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_account_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
) -> None:
    """Reject setup when the OAuth account no longer matches the entry."""
    mock_validate.side_effect = AccountMismatchError(
        "mismatch",
        context=ErrorContext(operation=Operation.ACCOUNT),
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_model_not_entitled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Load with a repair so the user can reconfigure a replacement model."""
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo(ACCOUNT_ID, "Home User", None),
        models=(ModelInfo("grok-other", "xai"),),
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    issue = issue_registry.async_get_issue(
        "spacexai",
        f"model_not_entitled_{conversation_subentry(mock_config_entry).subentry_id}",
    )
    assert issue is not None
    assert issue.is_fixable is False


@pytest.mark.usefixtures("setup_credentials", "mock_validate")
async def test_reconcile_skips_subentries_without_model(
    hass: HomeAssistant,
    provider_snapshot: ProviderSnapshot,
) -> None:
    """Ignore non-model subentries while reconciling catalog entitlement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home User",
        unique_id=ACCOUNT_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: DEFAULT_MODEL,
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_MAX_OUTPUT_TOKENS: DEFAULT_MAX_OUTPUT_TOKENS,
                },
                subentry_type="conversation",
                title="Grok",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={},
                subentry_type="metadata",
                title="No model",
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_reconcile_snapshot(hass, entry, provider_snapshot)
    assert hass.states.get(AGENT_ID) is not None


@pytest.mark.usefixtures("setup_credentials")
async def test_subscription_repair_is_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Create an actionable repair for an ineligible subscription."""
    mock_validate.side_effect = SubscriptionNotEntitledError(
        "not entitled",
        context=ErrorContext(operation=Operation.MODELS),
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    issue = issue_registry.async_get_issue(
        "spacexai", f"subscription_not_entitled_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.learn_more_url == "https://console.x.ai/"


@pytest.mark.usefixtures("setup_credentials")
async def test_subscription_repair_is_entry_scoped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
    provider_snapshot: ProviderSnapshot,
) -> None:
    """Keep subscription repairs isolated across config entries."""
    mock_validate.side_effect = SubscriptionNotEntitledError(
        "not entitled",
        context=ErrorContext(operation=Operation.MODELS),
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    issue_id = f"subscription_not_entitled_{mock_config_entry.entry_id}"
    other_issue_id = "subscription_not_entitled_other-entry"
    ir.async_create_issue(
        hass,
        "spacexai",
        other_issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="subscription_not_entitled",
    )

    mock_validate.side_effect = None
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo("healthy-account", "Healthy", None),
        models=provider_snapshot.models,
    )
    healthy_entry = MockConfigEntry(
        domain="spacexai",
        title="Healthy",
        unique_id="healthy-account",
        data=dict(mock_config_entry.data),
    )
    healthy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(healthy_entry.entry_id)
    assert issue_registry.async_get_issue("spacexai", issue_id)
    assert issue_registry.async_get_issue("spacexai", other_issue_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_subscription_repair_persists_across_transient_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Keep a subscription repair until setup positively validates the account."""
    mock_validate.side_effect = SubscriptionNotEntitledError(
        "not entitled",
        context=ErrorContext(operation=Operation.MODELS),
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    issue_id = f"subscription_not_entitled_{mock_config_entry.entry_id}"
    other_issue_id = "subscription_not_entitled_other-entry"
    ir.async_create_issue(
        hass,
        "spacexai",
        other_issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="subscription_not_entitled",
    )
    assert issue_registry.async_get_issue("spacexai", issue_id)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_validate.side_effect = ConnectionFailureError(
        "offline",
        context=ErrorContext(operation=Operation.MODELS),
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue("spacexai", issue_id)
    assert issue_registry.async_get_issue("spacexai", other_issue_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_subscription_repair_clears_on_successful_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
    provider_snapshot: ProviderSnapshot,
) -> None:
    """Clear a subscription repair only after a successful catalog snapshot."""
    issue_id = f"subscription_not_entitled_{mock_config_entry.entry_id}"
    ir.async_create_issue(
        hass,
        "spacexai",
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="subscription_not_entitled",
    )
    mock_validate.return_value = provider_snapshot
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert not issue_registry.async_get_issue("spacexai", issue_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_revokes_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Revoke the provider refresh token when the entry is removed."""
    with patch(
        "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
        new_callable=AsyncMock,
    ) as revoke:
        await async_remove_entry(hass, mock_config_entry)
    revoke.assert_awaited_once_with(REFRESH_TOKEN, "home-assistant-client", "")


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_skips_without_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log and skip revocation when the entry has no refresh token."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "token": {"access_token": ACCESS_TOKEN, "token_type": "Bearer"},
        },
    )
    with (
        patch(
            "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
            new_callable=AsyncMock,
        ) as revoke,
        caplog.at_level("WARNING"),
    ):
        await async_remove_entry(hass, mock_config_entry)
    revoke.assert_not_called()
    assert "reason=missing_refresh_token" in caplog.text
    assert ACCESS_TOKEN not in caplog.text


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_skips_unavailable_implementation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log and skip revocation when the OAuth implementation cannot be loaded."""
    with (
        patch(
            "homeassistant.components.spacexai.async_get_config_entry_implementation",
            side_effect=ImplementationUnavailableError(),
        ),
        patch(
            "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
            new_callable=AsyncMock,
        ) as revoke,
        caplog.at_level("WARNING"),
    ):
        await async_remove_entry(hass, mock_config_entry)
    revoke.assert_not_called()
    assert "reason=implementation_unavailable" in caplog.text
    assert REFRESH_TOKEN not in caplog.text
    assert ACCESS_TOKEN not in caplog.text


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_skips_foreign_implementation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Skip token revocation when the implementation is not a local OAuth client."""
    with (
        patch(
            "homeassistant.components.spacexai.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
            new_callable=AsyncMock,
        ) as revoke,
        caplog.at_level("WARNING"),
    ):
        await async_remove_entry(hass, mock_config_entry)
    revoke.assert_not_called()
    assert "reason=foreign_implementation" in caplog.text
    assert REFRESH_TOKEN not in caplog.text
    assert ACCESS_TOKEN not in caplog.text


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_logs_revocation_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Do not block removal when provider revocation fails."""
    with (
        patch(
            "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
            new_callable=AsyncMock,
            side_effect=ConnectionFailureError(
                "offline",
                context=ErrorContext(operation=Operation.REVOCATION),
            ),
        ),
        caplog.at_level("WARNING"),
    ):
        await async_remove_entry(hass, mock_config_entry)
    assert "category=connection_failure" in caplog.text
    assert REFRESH_TOKEN not in caplog.text
    assert ACCESS_TOKEN not in caplog.text


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_subentry_cleans_model_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Delete model repair issues when their subentry is removed."""
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo(ACCOUNT_ID, "Home User", None),
        models=(ModelInfo("grok-other", "xai"),),
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    issue_id = (
        f"model_not_entitled_{conversation_subentry(mock_config_entry).subentry_id}"
    )
    assert issue_registry.async_get_issue("spacexai", issue_id)

    hass.config_entries.async_remove_subentry(
        mock_config_entry, conversation_subentry(mock_config_entry).subentry_id
    )
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue("spacexai", issue_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_subentry_while_unloaded_cleans_model_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Clear model repairs when a subentry is deleted while the entry is unloaded."""
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo(ACCOUNT_ID, "Home User", None),
        models=(ModelInfo("grok-other", "xai"),),
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    subentry = conversation_subentry(mock_config_entry)
    issue_id = f"model_not_entitled_{subentry.subentry_id}"
    foreign_issue_id = "model_not_entitled_foreign-subentry"
    assert issue_registry.async_get_issue("spacexai", issue_id)
    ir.async_create_issue(
        hass,
        "spacexai",
        foreign_issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="model_not_entitled",
        translation_placeholders={"model": "grok-foreign"},
        data={
            "entry_id": "other-entry",
            "subentry_id": "foreign-subentry",
        },
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.config_entries.async_remove_subentry(mock_config_entry, subentry.subentry_id)
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue("spacexai", issue_id)
    assert issue_registry.async_get_issue("spacexai", foreign_issue_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_remove_cleans_account_repairs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Remove only the repair issues belonging to the removed account."""
    subentry = conversation_subentry(mock_config_entry)
    subscription_issue = f"subscription_not_entitled_{mock_config_entry.entry_id}"
    model_issue = f"model_not_entitled_{subentry.subentry_id}"
    ir.async_create_issue(
        hass,
        "spacexai",
        subscription_issue,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="subscription_not_entitled",
    )
    ir.async_create_issue(
        hass,
        "spacexai",
        model_issue,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="model_not_entitled",
        translation_placeholders={"model": "grok-old"},
        data={
            "entry_id": mock_config_entry.entry_id,
            "subentry_id": subentry.subentry_id,
        },
    )

    with patch(
        "homeassistant.components.spacexai.client.SpaceXAIClient.async_revoke",
        new_callable=AsyncMock,
    ):
        await async_remove_entry(hass, mock_config_entry)
    assert not issue_registry.async_get_issue("spacexai", subscription_issue)
    assert not issue_registry.async_get_issue("spacexai", model_issue)


async def test_setup_without_oauth_implementation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Retry setup until the configured OAuth implementation is available."""
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
