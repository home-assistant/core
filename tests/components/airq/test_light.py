"""Test the LIGHT platform from air-Q integration."""

from collections.abc import Awaitable, Callable
from typing import Protocol
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.airq import AirQCoordinator
from homeassistant.components.airq.light import (
    BRIGHTNESS_DEFAULT,
    LED_VALUE_SCALE,
    AirQLight,
    AirQLightEntityDescription,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode
from homeassistant.core import HomeAssistant
import homeassistant.util.color as color_util

from .common import TEST_DEVICE_DATA, TEST_DEVICE_INFO

ENTITY_ID = f"light.{TEST_DEVICE_INFO['name']}_led"


@pytest.mark.asyncio
async def test_entity_initialization(
    hass: HomeAssistant, registered_airq_config_entry
) -> None:
    """Test the initialisation of AirQLight entity."""
    coordinator = AirQCoordinator(hass, registered_airq_config_entry)
    coordinator.data = TEST_DEVICE_DATA

    description = AirQLightEntityDescription(
        key="airq_leds",
        translation_key="airq_leds",
        value=lambda data: data.get("brightness"),
    )
    entity = AirQLight(coordinator, description)

    assert entity.unique_id == f"{coordinator.device_id}_{description.key}"
    assert entity.supported_color_modes == {ColorMode.BRIGHTNESS}
    assert entity.color_mode == ColorMode.BRIGHTNESS


@pytest.fixture
def patch_aioairq_api(monkeypatch: pytest.MonkeyPatch) -> Callable[[float], None]:
    """Patch all aioairq.AirQ calls.

    Usage:
        patch_aioairq_api(led_brightness=5)
    """

    def _patch(led_brightness: float) -> None:
        monkeypatch.setattr(
            "aioairq.AirQ.fetch_device_info",
            AsyncMock(return_value=TEST_DEVICE_INFO),
        )
        monkeypatch.setattr(
            "aioairq.AirQ.get_latest_data",
            AsyncMock(return_value=TEST_DEVICE_DATA),
        )
        monkeypatch.setattr(
            "aioairq.AirQ.get_current_brightness",
            AsyncMock(return_value=led_brightness),
        )

    return _patch


class LightEntityFactory(Protocol):
    """Factory for creating AirQLight entities in Home Assistant.

    This callable initializes an AirQLight entity at a given brightness,
    sets up the underlying integration, and returns the HA entity object.
    """

    def __call__(self, *, led_brightness: float) -> Awaitable[AirQLight]:
        """Build and return an AirQLight with a specified LED brightness.

        Args:
            led_brightness (float): The brightness level for the LED (0.0–10.0).

        Returns:
            Awaitable[AirQLight]: An awaitable which, when awaited, yields the created entity.

        """
        raise NotImplementedError


@pytest.fixture
def light_entity_factory(
    hass: HomeAssistant,
    registered_airq_config_entry,
    patch_aioairq_api: Callable[[float], None],
) -> LightEntityFactory:
    """PyTest fixture returning a factory to spin up an AirQLight at a given brightness.

    This wraps the HA setup calls so that tests can simply `await factory(...)`
    to get a ready-to-use `AirQLight`.

    Returns:
        LightEntityFactory: A callable accepting `led_brightness` and producing the entity.

    """

    async def _create(led_brightness: float) -> AirQLight:
        """Patch call to aioairq with requested led_brightness and add AirQLight to hass.

        Args:
            led_brightness (float): The target LED brightness for the new entity.

        Returns:
            AirQLight: The created Home Assistant light entity.

        """
        patch_aioairq_api(led_brightness)
        await hass.config_entries.async_setup(registered_airq_config_entry.entry_id)
        await hass.async_block_till_done()
        return hass.data["light"].get_entity(ENTITY_ID)

    return _create


@pytest.mark.parametrize(
    ("led_initial_brightness", "expected_on", "expected_brightness"),
    [
        (5.0, True, color_util.value_to_brightness(LED_VALUE_SCALE, 5)),
        (0.0, False, None),
    ],
)
@pytest.mark.asyncio
async def test_turn_off_on_cycle(
    light_entity_factory: LightEntityFactory,
    led_initial_brightness: float,
    expected_on: bool,
    expected_brightness: int,
) -> None:
    """Test toggling the entity off then on from various initial LED brightnesses.

    Currently, if the device was added while being turned off, the entity will
    turn it on to the default brightness value. In other cases, previous
    brightness value will be restored.
    """
    light_entity = await light_entity_factory(led_brightness=led_initial_brightness)

    # ensure initial state lines up
    assert light_entity._attr_is_on == expected_on
    assert light_entity._attr_brightness == expected_brightness

    # turn off
    with patch("aioairq.AirQ.set_current_brightness", return_value=None):
        await light_entity.async_turn_off()
    assert not light_entity._attr_is_on
    # brightness attr sticks around even when off
    assert light_entity._attr_brightness == expected_brightness

    # turn back on without an explicit brightness
    with patch("aioairq.AirQ.set_current_brightness", return_value=None):
        await light_entity.async_turn_on()
    assert light_entity._attr_is_on

    # if initial was 0, fall back to BRIGHTNESS_DEFAULT
    recovered_brightness = (
        expected_brightness if led_initial_brightness else BRIGHTNESS_DEFAULT
    )
    assert light_entity._attr_brightness == recovered_brightness


@pytest.mark.asyncio
async def test_turn_on_with_explicit_brightness(
    light_entity_factory: LightEntityFactory,
) -> None:
    """Test that async_turn_on properly uses ATTR_BRIGHTNESS argument."""
    light_entity = await light_entity_factory(led_brightness=0.0)
    target = 100
    with patch("aioairq.AirQ.set_current_brightness", return_value=None):
        await light_entity.async_turn_on(**{ATTR_BRIGHTNESS: target})
    assert light_entity._attr_is_on
    assert light_entity._attr_brightness == target


@pytest.mark.asyncio
async def test_brightness_change_in_ha_state(
    hass: HomeAssistant, light_entity_factory: LightEntityFactory
) -> None:
    """Test that entity methods update the corresponding HA state too."""
    light_entity = await light_entity_factory(led_brightness=0.0)
    target_brightness = 100
    with patch("aioairq.AirQ.set_current_brightness", return_value=None):
        await light_entity.async_turn_on(**{ATTR_BRIGHTNESS: target_brightness})

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == target_brightness
