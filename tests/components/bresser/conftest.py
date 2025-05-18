"""Fixtures for Bresser integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioccl import CCLSensor
import pytest

from homeassistant.components.bresser.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WEBHOOK_ID = "040c273d"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Bresser Weather Station",
        domain=DOMAIN,
        data={
            CONF_WEBHOOK_ID: WEBHOOK_ID,
            CONF_HOST: "192.168.1.186",
            CONF_PORT: "8123",
        },
        unique_id="0000-0000",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.bresser.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_bresser() -> Generator[MagicMock]:
    """Return a mocked Bresser client."""
    with (
        patch(
            "homeassistant.components.bresser.coordinator.CCLDevice", autospec=True
        ) as bresser_mock,
    ):
        bresser = bresser_mock.return_value

        bresser._info = {
            "fw_ver": "1.0.0",
            "last_update_time": None,
            "mac_address": "48:31:B7:06:D5:60",
            "model": "HA100",
            "passkey": WEBHOOK_ID,
            "serial_no": "12345",
        }

        bresser._data = {"binary_sensors": {}, "sensors": {}}

        bresser.get_data.return_value = bresser._data

        # Store callbacks
        bresser._update_callback = None
        bresser._new_sensor_callbacks = set()

        def set_update_callback(callback):
            bresser._update_callback = callback

        bresser.set_update_callback.side_effect = set_update_callback

        def register_new_sensor_cb(callback):
            bresser._new_sensor_callbacks.add(callback)

        bresser.register_new_sensor_cb.side_effect = register_new_sensor_cb

        def remove_new_sensor_cb(callback):
            if callback in bresser._new_sensor_callbacks:
                bresser._new_sensor_callbacks.remove(callback)

        bresser.remove_new_sensor_cb.side_effect = remove_new_sensor_cb

        def update_info(info):
            for key, value in info.items():
                if key in bresser._info:
                    bresser._info[key] = value

        bresser.update_info.side_effect = update_info

        def process_data(data):
            new_sensors = []

            for key, value in data.items():
                if key not in bresser._data["sensors"]:
                    sensor = CCLSensor(key)
                    sensor.value = value
                    bresser._data["sensors"][key] = sensor
                    new_sensors.append(sensor)
                else:
                    bresser._data["sensors"][key].value = value

            for sensor in new_sensors:
                for callback in bresser._new_sensor_callbacks:
                    callback(sensor)

            if bresser._update_callback is not None:
                bresser._update_callback(bresser._data)

        bresser.process_data.side_effect = process_data

        yield bresser


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bresser: MagicMock,
) -> MockConfigEntry:
    """Set up the bresser integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
