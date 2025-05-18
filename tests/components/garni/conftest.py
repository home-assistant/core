"""Fixtures for garni integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioccl import CCLSensor
import pytest

from homeassistant.components.garni.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WEBHOOK_ID = "3fe58e09"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="GARNI Weather Station",
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
        "homeassistant.components.garni.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_garni() -> Generator[MagicMock]:
    """Return a mocked garni client."""
    with (
        patch(
            "homeassistant.components.garni.coordinator.CCLDevice", autospec=True
        ) as garni_mock,
    ):
        garni = garni_mock.return_value

        garni._info = {
            "fw_ver": "1.0.0",
            "last_update_time": None,
            "mac_address": "48:31:B7:06:D5:60",
            "model": "HA100",
            "passkey": WEBHOOK_ID,
            "serial_no": "12345",
        }

        garni._data = {"binary_sensors": {}, "sensors": {}}

        garni.get_data.return_value = garni._data

        # Store callbacks
        garni._update_callback = None
        garni._new_sensor_callbacks = set()

        def set_update_callback(callback):
            garni._update_callback = callback

        garni.set_update_callback.side_effect = set_update_callback

        def register_new_sensor_cb(callback):
            garni._new_sensor_callbacks.add(callback)

        garni.register_new_sensor_cb.side_effect = register_new_sensor_cb

        def remove_new_sensor_cb(callback):
            if callback in garni._new_sensor_callbacks:
                garni._new_sensor_callbacks.remove(callback)

        garni.remove_new_sensor_cb.side_effect = remove_new_sensor_cb

        def update_info(info):
            for key, value in info.items():
                if key in garni._info:
                    garni._info[key] = value

        garni.update_info.side_effect = update_info

        def process_data(data):
            new_sensors = []

            for key, value in data.items():
                if key not in garni._data["sensors"]:
                    sensor = CCLSensor(key)
                    sensor.value = value
                    garni._data["sensors"][key] = sensor
                    new_sensors.append(sensor)
                else:
                    garni._data["sensors"][key].value = value

            for sensor in new_sensors:
                for callback in garni._new_sensor_callbacks:
                    callback(sensor)

            if garni._update_callback is not None:
                garni._update_callback(garni._data)

        garni.process_data.side_effect = process_data

        yield garni


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_garni: MagicMock,
) -> MockConfigEntry:
    """Set up the garni integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
