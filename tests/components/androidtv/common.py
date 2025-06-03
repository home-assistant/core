"""Test code shared between test files."""

from typing import Any

from homeassistant.components.androidtv.const import (
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    DEFAULT_ADB_SERVER_PORT,
    DEFAULT_PORT,
    DEVICE_ANDROIDTV,
    DEVICE_FIRETV,
    DOMAIN,
)
from homeassistant.components.androidtv.entity import PREFIX_ANDROIDTV, PREFIX_FIRETV
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.util import slugify

from . import patchers

from tests.common import MockConfigEntry

ADB_PATCH_KEY = "patch_key"
TEST_ENTITY_NAME = "entity_name"
TEST_HOST_NAME = "127.0.0.1"

SHELL_RESPONSE_OFF = ""
SHELL_RESPONSE_STANDBY = "1"

# Android device with Python ADB implementation
CONFIG_ANDROID_PYTHON_ADB = {
    ADB_PATCH_KEY: patchers.KEY_PYTHON,
    TEST_ENTITY_NAME: f"{PREFIX_ANDROIDTV} {TEST_HOST_NAME}",
    DOMAIN: {
        CONF_HOST: TEST_HOST_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: DEVICE_ANDROIDTV,
    },
}

# Android device with Python ADB implementation imported from YAML
CONFIG_ANDROID_PYTHON_ADB_YAML = {
    ADB_PATCH_KEY: patchers.KEY_PYTHON,
    TEST_ENTITY_NAME: "ADB yaml import",
    DOMAIN: {
        CONF_NAME: "ADB yaml import",
        **CONFIG_ANDROID_PYTHON_ADB[DOMAIN],
    },
}

# Android device with Python ADB implementation with custom adbkey
CONFIG_ANDROID_PYTHON_ADB_KEY = {
    ADB_PATCH_KEY: patchers.KEY_PYTHON,
    TEST_ENTITY_NAME: CONFIG_ANDROID_PYTHON_ADB[TEST_ENTITY_NAME],
    DOMAIN: {
        **CONFIG_ANDROID_PYTHON_ADB[DOMAIN],
        CONF_ADBKEY: "user_provided_adbkey",
    },
}

# Android device with ADB server
CONFIG_ANDROID_ADB_SERVER = {
    ADB_PATCH_KEY: patchers.KEY_SERVER,
    TEST_ENTITY_NAME: f"{PREFIX_ANDROIDTV} {TEST_HOST_NAME}",
    DOMAIN: {
        CONF_HOST: TEST_HOST_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: DEVICE_ANDROIDTV,
        CONF_ADB_SERVER_IP: patchers.ADB_SERVER_HOST,
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    },
}

# Fire TV device with Python ADB implementation
CONFIG_FIRETV_PYTHON_ADB = {
    ADB_PATCH_KEY: patchers.KEY_PYTHON,
    TEST_ENTITY_NAME: f"{PREFIX_FIRETV} {TEST_HOST_NAME}",
    DOMAIN: {
        CONF_HOST: TEST_HOST_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: DEVICE_FIRETV,
    },
}

# Fire TV device with ADB server
CONFIG_FIRETV_ADB_SERVER = {
    ADB_PATCH_KEY: patchers.KEY_SERVER,
    TEST_ENTITY_NAME: f"{PREFIX_FIRETV} {TEST_HOST_NAME}",
    DOMAIN: {
        CONF_HOST: TEST_HOST_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: DEVICE_FIRETV,
        CONF_ADB_SERVER_IP: patchers.ADB_SERVER_HOST,
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    },
}

CONFIG_ANDROID_DEFAULT = CONFIG_ANDROID_PYTHON_ADB
CONFIG_FIRETV_DEFAULT = CONFIG_FIRETV_PYTHON_ADB


def setup_mock_entry(
    config: dict[str, Any],
    entity_domain: str,
    *,
    options=None,
    version=1,
    minor_version=2,
) -> tuple[str, str, MockConfigEntry]:
    """Prepare mock entry for entities tests."""
    patch_key = config[ADB_PATCH_KEY]
    entity_id = f"{entity_domain}.{slugify(config[TEST_ENTITY_NAME])}"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config[DOMAIN],
        unique_id="a1:b1:c1:d1:e1:f1",
        options=options,
        version=version,
        minor_version=minor_version,
    )

    return patch_key, entity_id, config_entry
