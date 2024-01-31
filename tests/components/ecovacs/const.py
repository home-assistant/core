"""Test ecovacs constants."""


from homeassistant.components.ecovacs.const import CONF_CONTINENT
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME

VALID_ENTRY_DATA = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_COUNTRY: "IT",
}

IMPORT_DATA = VALID_ENTRY_DATA | {CONF_CONTINENT: "EU"}
