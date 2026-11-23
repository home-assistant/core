"""Test SQL diagnostics."""

from typing import Any

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import CONF_DB_URL, Recorder
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sql.const import (
    CONF_ADDITIONAL_OPTIONS,
    CONF_COLUMN_NAME,
    CONF_QUERY,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant

from . import init_integration

OPTIONS = {
    CONF_QUERY: "SELECT 5 as value",
    CONF_COLUMN_NAME: "value",
    CONF_ADDITIONAL_OPTIONS: {
        CONF_UNIT_OF_MEASUREMENT: "MiB",
        CONF_VALUE_TEMPLATE: "{{ value }}",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_STATE_CLASS: SensorStateClass.TOTAL,
    },
}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="recorder_db"),
        pytest.param(
            {
                CONF_DB_URL: "mysql+pymysql://user:password@192.168.1.2:3306/homeassistant"
            },
            id="custom_db",
        ),
    ],
)
async def test_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await init_integration(hass, config=config, options=OPTIONS)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
