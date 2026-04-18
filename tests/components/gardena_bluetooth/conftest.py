"""Common fixtures for the Gardena Bluetooth tests."""

import asyncio
from collections.abc import Callable, Coroutine, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import bleak
from freezegun.api import FrozenDateTimeFactory
from gardena_bluetooth.client import Client
from gardena_bluetooth.const import DeviceInformation
from gardena_bluetooth.exceptions import CharacteristicNotFound
from gardena_bluetooth.parse import Characteristic, Service
from gardena_bluetooth.scan import (
    async_get_manufacturer_data as _async_get_manufacturer_data,
)
import pytest

from homeassistant.components.gardena_bluetooth.const import DOMAIN
from homeassistant.components.gardena_bluetooth.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_bluetooth

from . import WATER_TIMER_SERVICE_INFO, get_config_entry

from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True, scope="module")
def only_discover_this_domain() -> Generator[None]:
    """Only discover devices for this domain.

    This is needed to avoid interference from domains like
    gardena bluetooth that also matches on these devices.
    Which can cause async_block_till_done to wait too long
    waiting for advertisements that won't show up.
    """

    async def filtered_matches(hass: HomeAssistant):
        matchers = await async_get_bluetooth(hass)
        return [matcher for matcher in matchers if matcher["domain"] == DOMAIN]

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", new=filtered_matches
    ):
        yield


@pytest.fixture
def mock_entry():
    """Create hass config fixture."""
    return get_config_entry(WATER_TIMER_SERVICE_INFO)


@pytest.fixture(scope="module")
def mock_unload_entry() -> Generator[AsyncMock]:
    """Override async_unload_entry."""
    with patch(
        "homeassistant.components.gardena_bluetooth.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture(scope="module")
def mock_setup_entry(mock_unload_entry) -> Generator[AsyncMock]:
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


@pytest.fixture
async def scan_step(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Step system time forward."""

    freezer.move_to("2023-01-01T01:00:00Z")

    async def delay() -> None:
        """Trigger delay in system."""
        freezer.tick(delta=SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    return delay


@pytest.fixture(autouse=True)
def correct_scanners_and_clients_in_library(enable_bluetooth: None) -> Generator[None]:
    """Make sure the correct scanners and clients are used in the library.

    This is needed since home assistant overrides the bleak scanner and client with wrappers,
    but does so after enable_bluetooth fixture is applied, which causes the library to
    use the wrong classes.
    """
    with (
        patch("gardena_bluetooth.scan.BleakScanner", new=bleak.BleakScanner),
        patch("gardena_bluetooth.client.BleakClient", new=bleak.BleakClient),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_client(
    enable_bluetooth: None, scan_step, mock_read_char_raw: dict[str, Any]
) -> Generator[Mock]:
    """Auto mock bluetooth."""

    client_class = Mock()

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
        except KeyError:
            if default is SENTINEL:
                raise CharacteristicNotFound from KeyError
            return default
        return val

    def _all_char_uuid():
        return set(mock_read_char_raw.keys())

    def _all_char():
        product_type = client_class.call_args.args[1]
        services = Service.services_for_product_type(product_type)
        return {
            char.unique_id: char
            for service in services
            for char in service.characteristics.values()
            if char.uuid in mock_read_char_raw
        }

    client = Mock(spec_set=Client)
    client.read_char.side_effect = _read_char
    client.read_char_raw.side_effect = _read_char_raw
    client.get_all_characteristics_uuid.side_effect = _all_char_uuid
    client.get_all_characteristics.side_effect = _all_char
    client_class.return_value = client

    with (
        patch(
            "homeassistant.components.gardena_bluetooth.config_flow.Client",
            new=client_class,
        ),
        patch("homeassistant.components.gardena_bluetooth.Client", new=client_class),
    ):
        yield client


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.fixture
def manufacturer_request_event() -> Generator[asyncio.Event]:
    """Track manufacturer data requests with an event."""

    event = asyncio.Event()

    async def _get(*args, **kwargs):
        event.set()
        return await _async_get_manufacturer_data(*args, **kwargs)

    with (
        patch(
            "homeassistant.components.gardena_bluetooth.async_get_manufacturer_data",
            wraps=_get,
        ),
        patch(
            "homeassistant.components.gardena_bluetooth.config_flow.async_get_manufacturer_data",
            wraps=_get,
        ),
    ):
        yield event
