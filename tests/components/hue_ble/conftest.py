"""Common fixtures for the Hue BLE tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import generate_ble_device

from homeassistant.components.hue_ble.const import DOMAIN
from homeassistant.components.hue_ble.light import EffectType

from . import TEST_DEVICE_MAC, TEST_DEVICE_NAME


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hue_ble.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_scanner_count() -> Generator[AsyncMock]:
    """Override async_scanner_count."""
    with patch(
        "homeassistant.components.hue_ble.async_scanner_count", return_value=1
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_ble_device() -> Generator[AsyncMock]:
    """Override async_scanner_count."""
    with patch(
        "homeassistant.components.hue_ble.async_ble_device_from_address",
        return_value=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None):
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_DEVICE_NAME,
        unique_id=TEST_DEVICE_MAC.lower(),
        data={},
    )


@pytest.fixture
def mock_light() -> Generator[AsyncMock]:
    """Mock a Hue BLE light."""
    with patch(
        "homeassistant.components.hue_ble.HueBleLight", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.address = TEST_DEVICE_MAC
        client.maximum_mireds = 454
        client.minimum_mireds = 153
        client.name = TEST_DEVICE_NAME
        client.manufacturer = "Signify Netherlands B.V."
        client.model = "LTC004"
        client.firmware = "1.104.2"
        client.supports_colour_xy = True
        client.supports_colour_temp = True
        client.supports_brightness = True
        client.supports_on_off = True
        client.supports_effects = False
        client.available = True
        client.power_state = True
        client.brightness = 100
        client.colour_temp = 250
        client.colour_xy = (0.0, 0.0)
        client.colour_temp_mode = True
        client.effect = None
        client._state_changed_callbacks = []

        def add_callback_on_state_changed(function: Callable[[], None]):
            client._state_changed_callbacks.append(function)

        def remove_callback(function: Callable[[], None]) -> None:
            client._state_changed_callbacks.remove(function)

        def run_callbacks() -> None:
            [function() for function in client._state_changed_callbacks]

        async def mock_set_power(on: bool):
            client.power_state = on
            run_callbacks()

        async def mock_set_brightness(brightness: int):
            client.brightness = brightness
            run_callbacks()

        async def mock_set_colour_temp(colour_temp: int):
            client.colour_temp = colour_temp
            client.colour_temp_mode = True
            run_callbacks()

        async def mock_set_colour_xy(x: float, y: float):
            client.colour_xy = (x, y)
            client.colour_temp_mode = False
            run_callbacks()

        async def mock_set_effect(
            power: bool | None = None,
            brightness: int | None = None,
            colour: int | tuple[float, float] | None = None,
            effect: EffectType | None = None,
            effect_speed: int | None = None,
            transition: int | None = None,
        ):
            client.power_state = power or client.power_state
            client.brightness = brightness or client.brightness
            client.colour_temp = colour if type(colour) is int else client.colour_temp
            client.colour_xy = colour if type(colour) is tuple else client.colour_xy
            client.effect = (
                effect
                if effect is not None
                else (client.effect[0] if client.effect else None),
                effect_speed
                if effect_speed is not None
                else (client.effect[1] if client.effect else None),
            )
            client.colour_temp_mode = type(colour) is int
            run_callbacks()

        async def mock_set_temperature_effect(
            colour_temp: int, brightness: int, effect: EffectType, effect_speed: int
        ):
            client.colour_temp = colour_temp
            client.brightness = brightness
            client.effect = effect, effect_speed
            client.colour_temp_mode = True
            run_callbacks()

        client.add_callback_on_state_changed = add_callback_on_state_changed
        client.remove_callback = remove_callback
        client.set_power = AsyncMock(side_effect=mock_set_power)
        client.set_brightness = AsyncMock(side_effect=mock_set_brightness)
        client.set_colour_temp = AsyncMock(side_effect=mock_set_colour_temp)
        client.set_colour_xy = AsyncMock(side_effect=mock_set_colour_xy)
        client.set_effect = AsyncMock(side_effect=mock_set_effect)

        yield client
