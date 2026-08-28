"""Constants for the BLUETTI integration."""

DOMAIN: str = "bluetti"
INTEGRATION_NAME: str = "BLUETTI"

EVENT_TOKEN_EXPIRED: str = "onTokenExpired"
NOTIFY_ID_TOKEN_EXPIRED: str = "notifyTokenExpire"

# The cloud API has no per-account ID - one fixed unique_id per HA install.
ACCOUNT_UNIQUE_ID: str = "account"
