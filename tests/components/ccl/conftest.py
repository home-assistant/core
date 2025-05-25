"""Fixtures for ccl integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioccl import CCLSensor
import pytest

from homeassistant.components.ccl.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WEBHOOK_ID = "c2507426"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CCL Weather Station",
        domain=DOMAIN,
        data={
            CONF_WEBHOOK_ID: WEBHOOK_ID,
            CONF_HOST: "192.168.1.185",
            CONF_PORT: "8123",
        },
        unique_id="0000-0000",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.ccl.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_ccl() -> Generator[MagicMock]:
    """Return a mocked ccl client."""
    with (
        patch(
            "homeassistant.components.ccl.coordinator.CCLDevice", autospec=True
        ) as ccl_mock,
    ):
        ccl = ccl_mock.return_value

        ccl._info = {
            "fw_ver": "1.0.0",
            "last_update_time": None,
            "mac_address": "48:31:B7:06:D5:59",
            "model": "HA100",
            "passkey": WEBHOOK_ID,
            "serial_no": "12345",
        }

        ccl._data = {"binary_sensors": {}, "sensors": {}}

        ccl.get_data.return_value = ccl._data

        # Store callbacks
        ccl._update_callback = None
        ccl._new_sensor_callbacks = set()

        def set_update_callback(callback):
            ccl._update_callback = callback

        ccl.set_update_callback.side_effect = set_update_callback

        def register_new_sensor_cb(callback):
            ccl._new_sensor_callbacks.add(callback)

        ccl.register_new_sensor_cb.side_effect = register_new_sensor_cb

        def remove_new_sensor_cb(callback):
            if callback in ccl._new_sensor_callbacks:
                ccl._new_sensor_callbacks.remove(callback)

        ccl.remove_new_sensor_cb.side_effect = remove_new_sensor_cb

        def update_info(info):
            for key, value in info.items():
                if key in ccl._info:
                    ccl._info[key] = value

        ccl.update_info.side_effect = update_info

        def process_data(data):
            new_sensors = []

            for key, value in data.items():
                if key not in ccl._data["sensors"]:
                    sensor = CCLSensor(key)
                    sensor.value = value
                    ccl._data["sensors"][key] = sensor
                    new_sensors.append(sensor)
                else:
                    ccl._data["sensors"][key].value = value

            for sensor in new_sensors:
                for callback in ccl._new_sensor_callbacks:
                    callback(sensor)

            if ccl._update_callback is not None:
                ccl._update_callback(ccl._data)

        ccl.process_data.side_effect = process_data

        yield ccl


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ccl: MagicMock,
) -> MockConfigEntry:
    """Set up the ccl integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
