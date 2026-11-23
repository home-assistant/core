"""Test SQL diagnostics."""

from typing import Any

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import CONF_DB_URL, Recorder, get_instance
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


MYSQL_URL = "mysql+pymysql://user:password@192.168.1.2:3306/homeassistant"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("config", "options"),
    [
        pytest.param({}, OPTIONS, id="recorder_db"),
        pytest.param({CONF_DB_URL: MYSQL_URL}, OPTIONS, id="custom_db"),
        pytest.param({}, {**OPTIONS, CONF_DB_URL: MYSQL_URL}, id="db_url_in_options"),
    ],
)
async def test_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await init_integration(hass, config=config, options=options)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_diagnostics_explicit_recorder_db(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test an explicit URL of the recorder database counts as the recorder database."""
    entry = await init_integration(
        hass, config={CONF_DB_URL: get_instance(hass).db_url}, options=OPTIONS
    )

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["uses_recorder_db"] is True
