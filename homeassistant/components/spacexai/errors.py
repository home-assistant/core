"""Typed errors for the SpaceXAI integration."""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCategory(StrEnum):
    """Closed set of failures exposed by the integration."""

    AUTHENTICATION_REJECTED = "authentication_rejected"
    REFRESH_REJECTED = "refresh_rejected"
    REAUTHENTICATION_REQUIRED = "reauthentication_required"
    ACCOUNT_MISMATCH = "account_mismatch"
    SUBSCRIPTION_NOT_ENTITLED = "subscription_not_entitled"
    NO_CONVERSATION_MODELS = "no_conversation_models"
    MODEL_NOT_ENTITLED = "model_not_entitled"
    RATE_LIMITED = "rate_limited"
    QUOTA_LIMITED = "quota_limited"
    TIMEOUT = "timeout"
    CONNECTION_FAILURE = "connection_failure"
    TRANSIENT_PROVIDER_FAILURE = "transient_provider_failure"
    MALFORMED_PROVIDER_RESPONSE = "malformed_provider_response"
    INVALID_MODEL_TOOL_REQUEST = "invalid_model_tool_request"
    HOME_ASSISTANT_TOOL_FAILURE = "home_assistant_tool_failure"
    TOOL_LOOP_LIMIT = "tool_loop_limit"
    OUTPUT_LIMIT = "output_limit"
    PERMANENT_PROVIDER_FAILURE = "permanent_provider_failure"


class Operation(StrEnum):
    """Provider operation associated with a failure."""

    ACCOUNT = "account"
    MODELS = "models"
    RESPONSE = "response"
    REFRESH = "refresh"
    REVOCATION = "revocation"
    TOOL = "tool"


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorContext:
    """Sanitized provider error context."""

    operation: Operation
    model: str | None = None
    status: int | None = None
    provider_code: str | None = None
    request_id: str | None = None


class SpaceXAIError(Exception):
    """Base class for expected SpaceXAI failures."""

    category: ErrorCategory
    retryable: bool = False

    def __init__(self, message: str, *, context: ErrorContext) -> None:
        """Initialize a provider failure."""
        super().__init__(message)
        self.context = context


class AuthenticationRejectedError(SpaceXAIError):
    """The provider rejected credentials during initial authentication."""

    category = ErrorCategory.AUTHENTICATION_REJECTED


class RefreshRejectedError(SpaceXAIError):
    """The provider rejected the refresh token."""

    category = ErrorCategory.REFRESH_REJECTED


class ReauthenticationRequiredError(SpaceXAIError):
    """The active session must be reauthenticated."""

    category = ErrorCategory.REAUTHENTICATION_REQUIRED


class AccountMismatchError(SpaceXAIError):
    """The authenticated account does not match the config entry."""

    category = ErrorCategory.ACCOUNT_MISMATCH


class SubscriptionNotEntitledError(SpaceXAIError):
    """The account lacks subscription-backed API access."""

    category = ErrorCategory.SUBSCRIPTION_NOT_ENTITLED


class NoConversationModelsError(SpaceXAIError):
    """The account has no entitled text/conversation models."""

    category = ErrorCategory.NO_CONVERSATION_MODELS


class ModelNotEntitledError(SpaceXAIError):
    """The account is not entitled to the configured model."""

    category = ErrorCategory.MODEL_NOT_ENTITLED


class RateLimitedError(SpaceXAIError):
    """The provider rate limited the request."""

    category = ErrorCategory.RATE_LIMITED
    retryable = True


class QuotaLimitedError(SpaceXAIError):
    """The subscription allowance or quota is exhausted."""

    category = ErrorCategory.QUOTA_LIMITED


class RequestTimeoutError(SpaceXAIError):
    """The provider operation timed out."""

    category = ErrorCategory.TIMEOUT
    retryable = True


class ConnectionFailureError(SpaceXAIError):
    """The provider could not be reached."""

    category = ErrorCategory.CONNECTION_FAILURE
    retryable = True


class TransientProviderError(SpaceXAIError):
    """The provider reported a transient failure."""

    category = ErrorCategory.TRANSIENT_PROVIDER_FAILURE
    retryable = True


class MalformedProviderResponseError(SpaceXAIError):
    """The provider returned data that did not match its contract."""

    category = ErrorCategory.MALFORMED_PROVIDER_RESPONSE


class InvalidModelToolRequestError(SpaceXAIError):
    """The model emitted an invalid tool request."""

    category = ErrorCategory.INVALID_MODEL_TOOL_REQUEST


class ToolLoopLimitError(SpaceXAIError):
    """The bounded model/tool loop reached its limit."""

    category = ErrorCategory.TOOL_LOOP_LIMIT


class OutputLimitError(SpaceXAIError):
    """The provider reached the configured output-token limit."""

    category = ErrorCategory.OUTPUT_LIMIT


class PermanentProviderError(SpaceXAIError):
    """The provider permanently rejected a validly formed operation."""

    category = ErrorCategory.PERMANENT_PROVIDER_FAILURE
