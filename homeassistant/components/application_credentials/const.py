"""Constants for the Application Credentials integration."""

from homeassistant.backports.enum import StrEnum

DOMAIN = "application_credentials"


class ApplicationCredentialsType(StrEnum):
    """Application Credentials types."""

    AUTHORIZATION_SERVER = "authorization_server"
    CONFIG_CREDENTIAL = "config_credential"
