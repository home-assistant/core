"""Fixtures for Envisalink integration tests."""
from typing import Any
from unittest.mock import PropertyMock, patch

from pyenvisalink.alarm_panel import EnvisalinkAlarmPanel
from pyenvisalink.alarm_state import AlarmState
from pyenvisalink.const import (
    EVL4_MAX_ZONES,
    MAX_PARTITIONS,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.envisalink.const import (
    CONF_ALARM_NAME,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_DISCOVERY_PORT,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITION_SET,
    CONF_PASS,
    CONF_USERNAME,
    CONF_YAML_OPTIONS,
    CONF_ZONE_SET,
    CONF_ZONEDUMP_INTERVAL,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DOMAIN,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_TIMEOUT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_unique_id() -> str:
    """Return the default unique ID for the panel."""
    return "01:02:03:04:05:06"


@pytest.fixture
def mock_envisalink_alarm_panel(mock_unique_id):
    """Return a mocked EnvisalinkAlarmPanel."""
    with patch.object(
        EnvisalinkAlarmPanel,
        "discover",
        autospec=True,
        return_value=EnvisalinkAlarmPanel.ConnectionResult.SUCCESS,
    ), patch.object(
        EnvisalinkAlarmPanel,
        "discover_panel_type",
        autospec=True,
        return_value=EnvisalinkAlarmPanel.ConnectionResult.SUCCESS,
    ), patch.object(
        EnvisalinkAlarmPanel,
        "start",
        autospec=True,
        return_value=EnvisalinkAlarmPanel.ConnectionResult.SUCCESS,
    ), patch.object(
        EnvisalinkAlarmPanel, "is_online", autospec=True, return_value=True
    ), patch.object(
        EnvisalinkAlarmPanel,
        "mac_address",
        new_callable=PropertyMock,
        return_value=mock_unique_id,
    ), patch.object(
        EnvisalinkAlarmPanel,
        "panel_type",
        new_callable=PropertyMock,
        return_value=PANEL_TYPE_DSC,
    ), patch.object(
        EnvisalinkAlarmPanel,
        "envisalink_version",
        new_callable=PropertyMock,
        return_value=4,
    ), patch.object(
        EnvisalinkAlarmPanel,
        "alarm_state",
        new_callable=PropertyMock,
        return_value=AlarmState.get_initial_alarm_state(EVL4_MAX_ZONES, MAX_PARTITIONS),
    ), patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.get_max_zones_by_version",
        return_value=128,
    ):
        yield


def _build_config_data(for_result: bool) -> dict[str, Any]:
    in_input = {
        CONF_ALARM_NAME: "TestAlarmName",
    }
    in_both = {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASS: "test-password",
        CONF_ZONE_SET: "1-16",
        CONF_PARTITION_SET: "1",
        CONF_CODE: "1234",
        CONF_EVL_PORT: 4025,
        CONF_EVL_DISCOVERY_PORT: 80,
    }
    in_result = {
        CONF_EVL_VERSION: 4,
        CONF_PANEL_TYPE: PANEL_TYPE_DSC,
    }
    if for_result:
        return in_both | in_result
    return in_input | in_both


@pytest.fixture
def mock_config_data() -> dict[str, Any]:
    """Return the default input data for the config flow."""
    return _build_config_data(False)


@pytest.fixture
def mock_config_data_result() -> dict[str, Any]:
    """Return the default output data from the config flow."""
    return _build_config_data(True)


@pytest.fixture
def mock_config_entry(
    mock_config_data_result, mock_unique_id, mock_options_data_dsc
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data_result,
        unique_id=mock_unique_id,
        title="Test Alarm Name",
        options=mock_options_data_dsc,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_envisalink_alarm_panel
) -> MockConfigEntry:
    """Set up the Envisalink integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_config_entry_honeywell(
    mock_config_data_result, mock_unique_id, mock_options_data_honeywell
) -> MockConfigEntry:
    """Return the default mocked config entry for a Honeywell panel."""
    mock_config_data_result[CONF_PANEL_TYPE] = PANEL_TYPE_HONEYWELL
    mock_config_data_result.pop(CONF_CODE)
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data_result,
        unique_id=mock_unique_id,
        options=mock_options_data_honeywell,
    )


@pytest.fixture
def mock_config_entry_yaml_options(
    mock_config_data_result, mock_unique_id
) -> MockConfigEntry:
    """Return the default mocked config entry that contains the imported yaml options."""
    mock_config_data_result[CONF_YAML_OPTIONS] = {
        CONF_PANIC: "Police",
        CONF_EVL_KEEPALIVE: 60,
        CONF_ZONEDUMP_INTERVAL: 30,
        CONF_TIMEOUT: 10,
        CONF_CREATE_ZONE_BYPASS_SWITCHES: True,
    }
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data_result,
        unique_id=mock_unique_id,
        source=config_entries.SOURCE_IMPORT,
    )


def _build_yaml_import_data() -> dict[str, Any]:
    return {
        "host": "envisalink-host",
        "panel_type": PANEL_TYPE_DSC,
        "user_name": "USER",
        "password": "PASSWORD",
        "code": "1234",
        "port": 4025,
        "evl_version": 4,
        "keepalive_interval": 60,
        "zonedump_interval": 30,
        "timeout": 10,
        "panic_type": "Police",
        "zones": {
            1: {"name": "Entry Doors", "type": "opening"},
            2: {"name": "Motion Detectors", "type": "motion"},
            3: {"name": "Kid's Bedrooms", "type": "opening"},
            4: {"name": "Master Bedroom", "type": "opening"},
            5: {"name": "Kitchen", "type": "opening"},
            6: {"name": "Living/dining Room", "type": "opening"},
            7: {"name": "Family Room", "type": "opening"},
            8: {"name": "Basement", "type": "opening"},
        },
        "partitions": {
            1: {"name": "Home Alarm"},
        },
    }


@pytest.fixture
def mock_yaml_import_data() -> dict[str, Any]:
    """Return yaml configuration for import from configuration.yaml."""
    return _build_yaml_import_data()


@pytest.fixture
def mock_config_entry_yaml_import(mock_unique_id) -> MockConfigEntry:
    """Return the config data from after a configuration.yaml import."""
    data = _build_yaml_import_data()
    options = {}
    for key in CONF_PANIC, CONF_EVL_KEEPALIVE, CONF_ZONEDUMP_INTERVAL, CONF_TIMEOUT:
        options[key] = data[key]
        data.pop(key)
    data[CONF_ZONE_SET] = "1-8"
    data[CONF_PARTITION_SET] = "1"

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_unique_id,
        data=data,
        options=options,
    )


@pytest.fixture
def mock_options_data_dsc():
    """Return default configuration parameters for the options flow for DSC panels."""
    return {
        CONF_PANIC: "panic",
        CONF_EVL_KEEPALIVE: 60,
        CONF_ZONEDUMP_INTERVAL: 30,
        CONF_TIMEOUT: 10,
        CONF_CREATE_ZONE_BYPASS_SWITCHES: True,
    }


@pytest.fixture
def mock_options_data_honeywell():
    """Return default configuration parameters for the options flow for Honeywell panels."""
    return {
        CONF_PANIC: "panic",
        CONF_EVL_KEEPALIVE: 60,
        CONF_ZONEDUMP_INTERVAL: 30,
        CONF_TIMEOUT: 10,
        CONF_HONEYWELL_ARM_NIGHT_MODE: DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    }
