"""Constants for the Developer Credentials integration."""

from homeassistant.backports.enum import StrEnum

DOMAIN = "developer_credentials"


class DeveloperCredentialsType(StrEnum):
    """Developer Credentials types."""

    AUTHORIZATION_SERVER = "authorization_server"
    CONFIG_CREDENTIAL = "config_credential"
