"""Fixtures for Envisalink tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyenvisalink.alarm_state import AlarmState
import pytest

from homeassistant.components.envisalink.const import (
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITION_NUMBER,
    CONF_PARTITIONNAME,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONE_NUMBER,
    CONF_ZONENAME,
    CONF_ZONETYPE,
    DOMAIN,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.const import CONF_CODE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

# The configured alarm code, shared with the tests so the service-call
# assertions stay in sync with the code HA injects as the default.
MOCK_CODE = "1234"

MOCK_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_EVL_PORT: 4025,
    CONF_PANEL_TYPE: "DSC",
    CONF_EVL_VERSION: 3,
    CONF_USERNAME: "user",
    CONF_PASS: "pass",
}

MOCK_OPTIONS = {
    CONF_CODE: MOCK_CODE,
    CONF_PANIC: "Police",
}

MOCK_SUBENTRIES_DATA = [
    {
        "subentry_type": SUBENTRY_TYPE_PARTITION,
        "title": "Main Home (1)",
        "unique_id": f"{SUBENTRY_TYPE_PARTITION}_1",
        "data": {
            CONF_PARTITION_NUMBER: 1,
            CONF_PARTITIONNAME: "Main Home",
        },
    },
    {
        "subentry_type": SUBENTRY_TYPE_ZONE,
        "title": "Front Door (1)",
        "unique_id": f"{SUBENTRY_TYPE_ZONE}_1",
        "data": {
            CONF_ZONE_NUMBER: 1,
            CONF_ZONENAME: "Front Door",
            CONF_ZONETYPE: "door",
        },
    },
]

# Legacy YAML shape, still accepted for import.
MOCK_YAML_CONFIG = {
    DOMAIN: {
        CONF_HOST: "1.2.3.4",
        CONF_PANEL_TYPE: "DSC",
        CONF_USERNAME: "user",
        CONF_PASS: "pass",
        CONF_CODE: MOCK_CODE,
        "partitions": {1: {"name": "Main Home"}},
        "zones": {1: {"name": "Front Door", "type": "door"}},
    }
}

# Entity ids derived from the configured names.
ALARM_ENTITY = "alarm_control_panel.main_home"
KEYPAD_ENTITY = "sensor.main_home_keypad"
ZONE_ENTITY = "binary_sensor.front_door"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Envisalink config entry with a zone and a partition."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
        subentries_data=MOCK_SUBENTRIES_DATA,
    )


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Patch EnvisalinkAlarmPanel with an autospec'd mock controller.

    The integration waits on a connection future that is resolved by the
    login-success callback, so the mock's start() invokes it. Tests can
    reassign ``controller.start.side_effect`` to ``callback_login_failure`` or
    ``callback_login_timeout`` to exercise alternate connection outcomes.
    """
    with patch(
        "homeassistant.components.envisalink.EnvisalinkAlarmPanel", autospec=True
    ) as mock_panel:
        controller = mock_panel.return_value
        # (max_zones=64, max_partitions=8) — sized to the panel's hardware limits.
        controller.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        # A non-empty alpha makes the initial partition state DISARMED (not None).
        controller.alarm_state["partition"][1]["status"]["alpha"] = "Ready"
        controller.start.side_effect = lambda: controller.callback_login_success(None)
        # _client is a real (always-present) instance attribute on the
        # actual library object, but autospec only sees the class - it has
        # no idea this attribute exists, since it's only ever assigned
        # inside __init__. disconnect_panel() accesses it directly, so the
        # mock needs it set up to match.
        controller._client = MagicMock()
        controller._client._reconnect_task = None
        yield controller


async def setup_envisalink(
    hass: HomeAssistant, entry: MockConfigEntry | None = None
) -> bool:
    """Set up an envisalink config entry and wait for it to finish."""
    entry = entry or MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
        subentries_data=MOCK_SUBENTRIES_DATA,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return result


async def setup_envisalink_yaml(
    hass: HomeAssistant, config: ConfigType | None = None
) -> bool:
    """Set up the envisalink component from YAML and wait for import to finish."""
    result = await async_setup_component(hass, DOMAIN, config or MOCK_YAML_CONFIG)
    await hass.async_block_till_done()
    return result
