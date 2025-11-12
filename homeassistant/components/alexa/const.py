"""Constants for the Alexa integration.

CRITICAL FIX (2025-11-01): Changed OAuth scope from 'alexa::skills:account_linking'
to 'profile:user_id' for compatibility with Alexa Smart Home skills using Login with Amazon.
"""

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

# Domain
DOMAIN = "alexa"

# OAuth2 Endpoints (Amazon LWA)
AMAZON_AUTH_URL = "https://www.amazon.com/ap/oa"
AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
AMAZON_REVOKE_URL = "https://api.amazon.com/auth/o2/revoke"

# OAuth2 Scopes
# Required scope for Alexa Smart Home with Login with Amazon
REQUIRED_SCOPES = "profile:user_id"

# Timeouts (seconds)
OAUTH_TIMEOUT_SECONDS = 30
TOKEN_EXCHANGE_TIMEOUT_SECONDS = 30
TOKEN_REFRESH_TIMEOUT_SECONDS = 30

# Token Lifecycle
TOKEN_REFRESH_BUFFER_SECONDS = 300  # Refresh 5 minutes before expiry
TOKEN_EXPIRY_BUFFER_SECONDS = 300  # Refresh 5 minutes before expiry (alias)
TOKEN_CLOCK_SKEW_BUFFER_SECONDS = 60  # Allow 60 seconds of clock skew

# Storage
STORAGE_KEY_TOKENS = "alexa_oauth_tokens"
STORAGE_KEY = "alexa_oauth_tokens"  # Alias for backward compatibility
STORAGE_VERSION = 2  # Version 2 adds real encryption

# Config Flow
CONF_REDIRECT_URI = "redirect_uri"

# Error codes
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_INVALID_CODE = "invalid_code"
ERROR_INVALID_STATE = "invalid_state"
ERROR_UNKNOWN = "unknown"

# Phase 3: YAML Migration
YAML_CONFIG_SECTION = "alexa"
YAML_CONFIG_FILENAME = "configuration.yaml"
YAML_MIGRATION_MARKER = ".alexa_migrated"
YAML_BACKUP_SUFFIX = ".alexa_backup"

# Phase 3: Advanced Reauth
REAUTH_REASON_REFRESH_TOKEN_EXPIRED = "refresh_token_expired"
REAUTH_REASON_APP_REVOKED = "app_revoked"
REAUTH_REASON_CLIENT_SECRET_ROTATED = "client_secret_rotated"
REAUTH_REASON_REGIONAL_CHANGE = "regional_change"
REAUTH_REASON_SCOPE_CHANGED = "scope_changed"

# Phase 3: Reauth Detection
REAUTH_MAX_RETRY_ATTEMPTS = 3
REAUTH_RETRY_DELAY_SECONDS = 5
REAUTH_BACKOFF_MULTIPLIER = 2

# Phase 3: Regional Endpoints (Amazon LWA regions)
REGIONAL_ENDPOINTS = {
    "na": {  # North America
        "auth_url": "https://www.amazon.com/ap/oa",
        "token_url": "https://api.amazon.com/auth/o2/token",
        "revoke_url": "https://api.amazon.com/auth/o2/revoke",
    },
    "eu": {  # Europe
        "auth_url": "https://www.amazon.co.uk/ap/oa",
        "token_url": "https://api.amazon.co.uk/auth/o2/token",
        "revoke_url": "https://api.amazon.co.uk/auth/o2/revoke",
    },
    "fe": {  # Far East
        "auth_url": "https://www.amazon.co.jp/ap/oa",
        "token_url": "https://api.amazon.co.jp/auth/o2/token",
        "revoke_url": "https://api.amazon.co.jp/auth/o2/revoke",
    },
}

# Phase 3: Migration Storage
MIGRATION_STORAGE_KEY = "alexa_migration_state"
MIGRATION_STORAGE_VERSION = 1
