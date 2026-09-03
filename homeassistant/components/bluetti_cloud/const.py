"""Constants for the BLUETTI integration."""

DOMAIN: str = "bluetti_cloud"
INTEGRATION_NAME: str = "BLUETTI"

SSO_URL: str = "https://sso.bluettipower.com"
GATEWAY_URL: str = "https://gw.bluettipower.com"
WSS_URL: str = "wss://gw.bluettipower.com/api/edgeiotgw/ws-coordination"


def token_expired_signal(entry_id: str) -> str:
    """Dispatcher signal fired when the cloud reports an entry's token as expired.

    Entry-scoped rather than a single bus-wide event: two accounts (two
    entries) each have their own token, so one's expiry must not wake the
    other's listener.
    """
    return f"{DOMAIN}_token_expired_{entry_id}"


# The cloud API has no per-account ID - one fixed unique_id per HA install.
ACCOUNT_UNIQUE_ID: str = "account"
