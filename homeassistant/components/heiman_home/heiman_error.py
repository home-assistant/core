"""Error definitions for Heiman Home integration."""

from enum import Enum


class HeimanErrorCode(int, Enum):
    """Heiman Cloud error codes."""

    # General errors
    SUCCESS = 0
    UNKNOWN_ERROR = -1

    # Configuration errors
    CODE_CONFIG_INVALID_INPUT = 100
    CODE_CONFIG_INVALID_STATE = 101
    CODE_CONFIG_FLOW_ERROR = 102

    # OAuth2 errors
    CODE_OAUTH_UNAUTHORIZED = 200
    CODE_OAUTH_INVALID_RESPONSE = 201
    CODE_OAUTH_INVALID_CODE = 202
    CODE_OAUTH_INVALID_REFRESH_TOKEN = 203

    # HTTP errors
    CODE_HTTP_ERROR = 300
    CODE_HTTP_UNAUTHORIZED = 301
    CODE_HTTP_INVALID_ACCESS_TOKEN = 302
    CODE_HTTP_FORBIDDEN = 403
    CODE_HTTP_NOT_FOUND = 404
    CODE_HTTP_TIMEOUT = 408

    # JSON errors
    CODE_JSON_DECODE_ERROR = 500
    CODE_JSON_ENCODE_ERROR = 501

    # API errors
    CODE_API_ERROR = 600
    CODE_API_RATE_LIMIT = 601
    CODE_API_SERVER_ERROR = 602

    # Authentication errors
    AUTH_INVALID_CREDENTIALS = 1001
    AUTH_TOKEN_EXPIRED = 1002
    AUTH_INVALID_TOKEN = 1003
    AUTH_PERMISSION_DENIED = 1004

    # Device errors
    DEVICE_NOT_FOUND = 3001
    DEVICE_OFFLINE = 3002
    DEVICE_BUSY = 3003
    DEVICE_ERROR = 3004

    # Network errors
    NETWORK_ERROR = 4001
    NETWORK_TIMEOUT = 4002
    NETWORK_UNREACHABLE = 4003

    # MQTT errors
    MQTT_CONNECTION_FAILED = 5001
    MQTT_AUTH_FAILED = 5002
    MQTT_SUBSCRIBE_FAILED = 5003


class HeimanError(Exception):
    """Base exception for Heiman Home integration."""

    def __init__(
        self,
        message: str,
        error_code: HeimanErrorCode = HeimanErrorCode.UNKNOWN_ERROR,
        details: dict | None = None,
    ):
        """Initialize Heiman error."""
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return the formatted error message."""
        details_str = f" - {self.details}" if self.details else ""
        return f"[{self.error_code}] {self.message}{details_str}"


class HeimanAuthError(HeimanError):
    """Authentication related errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: HeimanErrorCode = HeimanErrorCode.AUTH_INVALID_CREDENTIALS,
        details: dict | None = None,
    ):
        """Initialize authentication error."""
        super().__init__(message, error_code, details)


class HeimanTokenError(HeimanError):
    """Token related errors."""

    def __init__(
        self,
        message: str = "Token error",
        error_code: HeimanErrorCode = HeimanErrorCode.AUTH_TOKEN_EXPIRED,
        details: dict | None = None,
    ):
        """Initialize token error."""
        super().__init__(message, error_code, details)


class HeimanApiError(HeimanError):
    """API request related errors."""

    def __init__(
        self,
        message: str = "API request failed",
        error_code: HeimanErrorCode = HeimanErrorCode.CODE_API_ERROR,
        details: dict | None = None,
    ):
        """Initialize API error."""
        super().__init__(message, error_code, details)


class HeimanDeviceError(HeimanError):
    """Device related errors."""

    def __init__(
        self,
        message: str = "Device error",
        error_code: HeimanErrorCode = HeimanErrorCode.DEVICE_ERROR,
        details: dict | None = None,
    ):
        """Initialize device error."""
        super().__init__(message, error_code, details)


class HeimanMqttError(HeimanError):
    """MQTT related errors."""

    def __init__(
        self,
        message: str = "MQTT error",
        error_code: HeimanErrorCode = HeimanErrorCode.MQTT_CONNECTION_FAILED,
        details: dict | None = None,
    ):
        """Initialize MQTT error."""
        super().__init__(message, error_code, details)


class HeimanNetworkError(HeimanError):
    """Network related errors."""

    def __init__(
        self,
        message: str = "Network error",
        error_code: HeimanErrorCode = HeimanErrorCode.NETWORK_ERROR,
        details: dict | None = None,
    ):
        """Initialize network error."""
        super().__init__(message, error_code, details)


class HeimanConfigError(HeimanError):
    """Configuration related errors."""

    def __init__(
        self,
        message: str = "Configuration error",
        error_code: HeimanErrorCode = HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
        details: dict | None = None,
    ):
        """Initialize configuration error."""
        super().__init__(message, error_code, details)
