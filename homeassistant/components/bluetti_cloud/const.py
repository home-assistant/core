"""Constants for the BLUETTI integration."""

DOMAIN: str = "bluetti_cloud"
INTEGRATION_NAME: str = "BLUETTI"

SSO_URL: str = "https://sso.bluettipower.com"
GATEWAY_URL: str = "https://gw.bluettipower.com"
WSS_URL: str = "wss://gw.bluettipower.com/api/edgeiotgw/ws-coordination"

EVENT_TOKEN_EXPIRED: str = "onTokenExpired"
NOTIFY_ID_TOKEN_EXPIRED: str = "notifyTokenExpire"

# The cloud API has no per-account ID - one fixed unique_id per HA install.
ACCOUNT_UNIQUE_ID: str = "account"
