"""Test ecovacs constants."""


from homeassistant.components.ecovacs.const import CONF_CONTINENT, InstanceMode
from homeassistant.const import CONF_COUNTRY, CONF_MODE, CONF_PASSWORD, CONF_USERNAME

CONFIG_DATA_WITHOUT_MODE = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_COUNTRY: "IT",
}

VALID_ENTRY_DATA = CONFIG_DATA_WITHOUT_MODE | {
    CONF_MODE: InstanceMode.CLOUD,
}

IMPORT_DATA = CONFIG_DATA_WITHOUT_MODE | {CONF_CONTINENT: "EU"}
