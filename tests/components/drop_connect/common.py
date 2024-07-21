"""Define common test values."""

from syrupy import SnapshotAssertion

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

TEST_DATA_HUB_TOPIC = "drop_connect/DROP-1_C0FFEE/255"
TEST_DATA_HUB = (
    '{"curFlow":5.77,"peakFlow":13.8,"usedToday":232.77,"avgUsed":76,"psi":62.2,"psiLow":61,"psiHigh":62,'
    '"water":1,"bypass":0,"pMode":"home","battery":50,"notif":1,"leak":0}'
)
TEST_DATA_HUB_RESET = (
    '{"curFlow":0,"peakFlow":0,"usedToday":0,"avgUsed":0,"psi":0,"psiLow":0,"psiHigh":0,'
    '"water":0,"bypass":1,"pMode":"away","battery":0,"notif":0,"leak":0}'
)

TEST_DATA_SALT_TOPIC = "drop_connect/DROP-1_C0FFEE/8"
TEST_DATA_SALT = '{"salt":1}'
TEST_DATA_SALT_RESET = '{"salt":0}'

TEST_DATA_LEAK_TOPIC = "drop_connect/DROP-1_C0FFEE/20"
TEST_DATA_LEAK = '{"battery":100,"leak":1,"temp":68.2}'
TEST_DATA_LEAK_RESET = '{"battery":0,"leak":0,"temp":0}'

TEST_DATA_SOFTENER_TOPIC = "drop_connect/DROP-1_C0FFEE/0"
TEST_DATA_SOFTENER = (
    '{"curFlow":5.0,"bypass":0,"battery":20,"capacity":1000,"resInUse":1,"psi":50.5}'
)
TEST_DATA_SOFTENER_RESET = (
    '{"curFlow":0,"bypass":1,"battery":0,"capacity":0,"resInUse":0,"psi":null}'
)

TEST_DATA_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/4"
TEST_DATA_FILTER = '{"curFlow":19.84,"bypass":0,"battery":12,"psi":38.2}'
TEST_DATA_FILTER_RESET = '{"curFlow":0,"bypass":1,"battery":0,"psi":null}'

TEST_DATA_PROTECTION_VALVE_TOPIC = "drop_connect/DROP-1_C0FFEE/78"
TEST_DATA_PROTECTION_VALVE = (
    '{"curFlow":7.1,"psi":61.3,"water":1,"battery":0,"leak":1,"temp":70.5}'
)
TEST_DATA_PROTECTION_VALVE_RESET = (
    '{"curFlow":0,"psi":0,"water":0,"battery":0,"leak":0,"temp":0}'
)

TEST_DATA_PUMP_CONTROLLER_TOPIC = "drop_connect/DROP-1_C0FFEE/83"
TEST_DATA_PUMP_CONTROLLER = '{"curFlow":2.2,"psi":62.2,"pump":1,"leak":1,"temp":68.8}'
TEST_DATA_PUMP_CONTROLLER_RESET = '{"curFlow":0,"psi":0,"pump":0,"leak":0,"temp":0}'

TEST_DATA_RO_FILTER_TOPIC = "drop_connect/DROP-1_C0FFEE/95"
TEST_DATA_RO_FILTER = (
    '{"leak":1,"tdsIn":164,"tdsOut":9,"cart1":59,"cart2":80,"cart3":59}'
)
TEST_DATA_RO_FILTER_RESET = (
    '{"leak":0,"tdsIn":0,"tdsOut":0,"cart1":0,"cart2":0,"cart3":0}'
)


def config_entry_hub() -> ConfigEntry:
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


def config_entry_salt() -> ConfigEntry:
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


def config_entry_leak() -> ConfigEntry:
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


def config_entry_softener() -> ConfigEntry:
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


def config_entry_filter() -> ConfigEntry:
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


def config_entry_protection_valve() -> ConfigEntry:
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


def config_entry_pump_controller() -> ConfigEntry:
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


def config_entry_ro_filter() -> ConfigEntry:
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


def help_assert_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: ConfigEntry,
    step: str,
    assert_unknown: bool = False,
) -> None:
    """Assert platform entities and state."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    if assert_unknown:
        for entity_entry in entity_entries:
            assert hass.states.get(entity_entry.entity_id).state == STATE_UNKNOWN
        return

    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-{step}"
        )
