"""The tests for Satel Integra integration."""

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.satel_integra.const import (
    CONF_ARM_HOME_MODE,
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

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_CODE = "1234"
MOCK_CONFIG_DATA = {CONF_HOST: "192.168.0.2", CONF_PORT: DEFAULT_PORT}
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


def get_monitor_callbacks(
    mock_satel: AsyncMock,
) -> tuple[
    Callable[[], None],
    Callable[[dict[int, int]], None],
    Callable[[dict[int, int]], None],
]:
    """Return callbacks passed to `register_callbacks`."""
    if not mock_satel.register_callbacks.call_args_list:
        pytest.fail("register_callbacks was not called")

    call = mock_satel.register_callbacks.call_args_list[-1]
    if call.kwargs:
        partitions_cb = call.kwargs["alarm_status_callback"]
        zones_cb = call.kwargs["zone_changed_callback"]
        outputs_cb = call.kwargs["output_changed_callback"]
    else:
        partitions_cb, zones_cb, outputs_cb = call.args

    return partitions_cb, zones_cb, outputs_cb
