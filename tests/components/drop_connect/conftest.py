"""Define fixtures available for all tests."""
import pytest

from homeassistant.components.drop_connect.const import (
    CONF_COMMAND_TOPIC,
    CONF_DATA_TOPIC,
    CONF_DEVICE_DESC,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OWNER_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry_hub(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_255",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/255/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/255/#",
            CONF_DEVICE_DESC: "Hub",
            CONF_DEVICE_ID: 255,
            CONF_DEVICE_NAME: "Hub DROP-1_C0FFEE",
            CONF_DEVICE_TYPE: "hub",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_salt(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_8",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/8/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/8/#",
            CONF_DEVICE_DESC: "Salt Sensor",
            CONF_DEVICE_ID: 8,
            CONF_DEVICE_NAME: "Salt Sensor",
            CONF_DEVICE_TYPE: "salt",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_leak(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_20",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/20/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/20/#",
            CONF_DEVICE_DESC: "Leak Detector",
            CONF_DEVICE_ID: 20,
            CONF_DEVICE_NAME: "Leak Detector",
            CONF_DEVICE_TYPE: "leak",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_softener(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_0",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/0/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/0/#",
            CONF_DEVICE_DESC: "Softener",
            CONF_DEVICE_ID: 0,
            CONF_DEVICE_NAME: "Softener",
            CONF_DEVICE_TYPE: "soft",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_filter(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_4",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/4/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/4/#",
            CONF_DEVICE_DESC: "Filter",
            CONF_DEVICE_ID: 4,
            CONF_DEVICE_NAME: "Filter",
            CONF_DEVICE_TYPE: "filt",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_protection_valve(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_78",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/78/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/78/#",
            CONF_DEVICE_DESC: "Protection Valve",
            CONF_DEVICE_ID: 78,
            CONF_DEVICE_NAME: "Protection Valve",
            CONF_DEVICE_TYPE: "pv",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_pump_controller(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_83",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/83/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/83/#",
            CONF_DEVICE_DESC: "Pump Controller",
            CONF_DEVICE_ID: 83,
            CONF_DEVICE_NAME: "Pump Controller",
            CONF_DEVICE_TYPE: "pc",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )


@pytest.fixture
def config_entry_ro_filter(hass: HomeAssistant):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="DROP-1_C0FFEE_255",
        data={
            CONF_COMMAND_TOPIC: "drop_connect/DROP-1_C0FFEE/95/cmd",
            CONF_DATA_TOPIC: "drop_connect/DROP-1_C0FFEE/95/#",
            CONF_DEVICE_DESC: "RO Filter",
            CONF_DEVICE_ID: 95,
            CONF_DEVICE_NAME: "RO Filter",
            CONF_DEVICE_TYPE: "ro",
            CONF_HUB_ID: "DROP-1_C0FFEE",
            CONF_DEVICE_OWNER_ID: "DROP-1_C0FFEE_255",
        },
        version=1,
    )
