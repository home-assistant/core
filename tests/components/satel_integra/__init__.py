"""The tests for Satel Integra integration."""

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.satel_integra.const import (
    CONF_ARM_HOME_MODE,
    CONF_ENABLE_TEMPERATURE_SENSOR,
    CONF_ENCRYPTION_KEY,
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    DEFAULT_PORT,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

MOCK_CODE = "1234"
MOCK_CONFIG_DATA = {
    CONF_HOST: "192.168.0.2",
    CONF_PORT: DEFAULT_PORT,
    CONF_ENCRYPTION_KEY: "encryption_key",
}
MOCK_CONFIG_OPTIONS = {CONF_CODE: MOCK_CODE}

MOCK_ENTRY_ID = "1234567890"

MOCK_PARTITION_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_PARTITION,
    subentry_id="ID_PARTITION",
    unique_id="partition_1",
    title="Home (1)",
    data={
        CONF_NAME: "Home",
        CONF_ARM_HOME_MODE: 1,
        CONF_PARTITION_NUMBER: 1,
    },
)

MOCK_ZONE_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_ZONE,
    subentry_id="ID_ZONE",
    unique_id="zone_1",
    title="Zone (1)",
    data={
        CONF_ENABLE_TEMPERATURE_SENSOR: False,
        CONF_NAME: "Zone",
        CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
        CONF_ZONE_NUMBER: 1,
    },
)

MOCK_ZONE_TEMPERATURE_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_ZONE,
    subentry_id="ID_ZONE",
    unique_id="zone_1",
    title="Zone (1)",
    data={
        CONF_ENABLE_TEMPERATURE_SENSOR: True,
        CONF_NAME: "Zone",
        CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
        CONF_ZONE_NUMBER: 1,
    },
)

MOCK_OUTPUT_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_OUTPUT,
    subentry_id="ID_OUTPUT",
    unique_id="output_1",
    title="Output (1)",
    data={
        CONF_NAME: "Output",
        CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
        CONF_OUTPUT_NUMBER: 1,
    },
)

MOCK_SWITCHABLE_OUTPUT_SUBENTRY = ConfigSubentry(
    subentry_type=SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    subentry_id="ID_SWITCHABLE_OUTPUT",
    unique_id="switchable_output_1",
    title="Switchable Output (1)",
    data={
        CONF_NAME: "Switchable Output",
        CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
    },
)


@pytest.mark.usefixtures("patch_debounce")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _get_registered_callback(
    callback_method: Mock, callback_name: str
) -> Callable[[], None]:
    """Return the callback passed to a registration method."""
    if not callback_method.call_args_list:
        pytest.fail(f"{callback_name} callback was not registered")

    return callback_method.call_args_list[-1].args[0]


def get_alarm_status_callback(mock_satel: AsyncMock) -> Callable[[], None]:
    """Return the registered alarm status callback."""
    return _get_registered_callback(
        mock_satel.add_alarm_status_callback, "Alarm status"
    )


def get_zone_changed_callback(mock_satel: AsyncMock) -> Callable[[], None]:
    """Return the registered zone changed callback."""
    return _get_registered_callback(
        mock_satel.add_zone_changed_callback, "Zone changed"
    )


def get_output_changed_callback(mock_satel: AsyncMock) -> Callable[[], None]:
    """Return the registered output changed callback."""
    return _get_registered_callback(
        mock_satel.add_output_changed_callback, "Output changed"
    )


def get_system_status_callback(mock_satel: AsyncMock) -> Callable[[], None]:
    """Return the registered system status callback."""
    return _get_registered_callback(
        mock_satel.add_system_status_callback, "System status"
    )


async def trigger_connection_status_update(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    status: bool,
) -> None:
    """Trigger a connection status update."""
    mock_satel.connected = status
    for call in mock_satel.add_connection_status_callback.call_args_list:
        call[0][0]()
    await hass.async_block_till_done()
