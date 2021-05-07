"""Constants for the securitas direct integration."""

# domain
DOMAIN = "securitas_direct"

# configuration properties
CONF_COUNTRY = "country"
CONF_LANG = "lang"
CONF_INSTALLATION = "installation"

# config flow
STEP_USER = "user"
STEP_REAUTH = "reauth_confirm"
MULTI_SEC_CONFIGS = "multiple_securitas_configs"
UNABLE_TO_CONNECT = "unable_to_connect"
SECURITAS_DIRECT_PLATFORMS = [
    "alarm_control_panel",
]
