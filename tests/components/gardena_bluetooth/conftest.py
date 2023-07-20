"""Common fixtures for the Gardena Bluetooth tests."""
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from gardena_bluetooth.client import Client
from gardena_bluetooth.const import DeviceInformation
from gardena_bluetooth.exceptions import CharacteristicNotFound
from gardena_bluetooth.parse import Characteristic
import pytest

from homeassistant.components.gardena_bluetooth.const import DOMAIN
from homeassistant.const import CONF_ADDRESS

from . import WATER_TIMER_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry():
    """Create hass config fixture."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: WATER_TIMER_SERVICE_INFO.address}
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gardena_bluetooth.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_read_char_raw():
    """Mock data on device."""
    return {
        DeviceInformation.firmware_version.uuid: b"1.2.3",
        DeviceInformation.model_number.uuid: b"Mock Model",
    }


@pytest.fixture(autouse=True)
def mock_client(enable_bluetooth: None, mock_read_char_raw: dict[str, Any]) -> None:
    """Auto mock bluetooth."""

    client = Mock(spec_set=Client)

    SENTINEL = object()

    def _read_char(char: Characteristic, default: Any = SENTINEL):
        try:
            return char.decode(mock_read_char_raw[char.uuid])
        except KeyError:
            if default is SENTINEL:
                raise CharacteristicNotFound from KeyError
            return default

    def _read_char_raw(uuid: str, default: Any = SENTINEL):
        try:
            val = mock_read_char_raw[uuid]
            if isinstance(val, Exception):
                raise val
            return val
        except KeyError:
            if default is SENTINEL:
                raise CharacteristicNotFound from KeyError
            return default

    def _all_char():
        return set(mock_read_char_raw.keys())

    client.read_char.side_effect = _read_char
    client.read_char_raw.side_effect = _read_char_raw
    client.get_all_characteristics_uuid.side_effect = _all_char

    with patch(
        "homeassistant.components.gardena_bluetooth.config_flow.Client",
        return_value=client,
    ), patch(
        "homeassistant.components.gardena_bluetooth.Client", return_value=client
    ), freeze_time(
        "2023-01-01", tz_offset=1
    ):
        yield client


@pytest.fixture(autouse=True)
def enable_all_entities():
    """Make sure all entities are enabled."""
    with patch(
        "homeassistant.components.gardena_bluetooth.coordinator.GardenaBluetoothEntity.entity_registry_enabled_default",
        new=Mock(return_value=True),
    ):
        yield
