"""Test the Tridonic DALI light platform."""

from unittest.mock import AsyncMock, patch

from dali.exceptions import TransmissionError
from dali.gear.general import DAPC
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.dali.const import DOMAIN
from homeassistant.components.dali.coordinator import (
    DaliCoordinator,
    DaliGearData,
    _brightness_to_dali_level,
    _dali_level_to_brightness,
)
from homeassistant.components.dali.light import DaliLight, _is_light
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN, ColorMode
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDaliDriver


async def test_light_commands_clamp_dali_mask(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test light commands never send DALI's mask value as brightness."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyACM0"},
        title="USB-DALI2",
    )
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {
        0: DaliGearData(level=128, min_level=86, linear_dimming=True, device_types=(6,))
    }
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with patch.object(coordinator, "async_update_gear", new_callable=AsyncMock):
        await light.async_turn_on(brightness=255)
    assert isinstance(fake_dali_driver.sent[-1], DAPC)
    assert fake_dali_driver.sent[-1].power == 254

    with patch.object(coordinator, "async_update_gear", new_callable=AsyncMock):
        await light.async_turn_off()
    assert isinstance(fake_dali_driver.sent[-1], DAPC)
    assert fake_dali_driver.sent[-1].power == 0


async def test_light_command_failure_raises_home_assistant_error(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test DALI communication errors are surfaced as Home Assistant errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyACM0"},
        title="USB-DALI2",
    )
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {
        0: DaliGearData(level=128, min_level=86, linear_dimming=True, device_types=(6,))
    }
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with (
        patch.object(fake_dali_driver, "send", side_effect=OSError("serial failure")),
        pytest.raises(HomeAssistantError),
    ):
        await light.async_turn_off()


async def test_light_properties(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test basic light properties."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {0: DaliGearData(level=128, min_level=86, device_types=(6,))}
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    assert light.available
    assert light.is_on
    assert light.brightness == 128
    assert light.color_mode is ColorMode.BRIGHTNESS
    assert light.supported_color_modes == {ColorMode.BRIGHTNESS}


async def test_light_unknown_state(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a gear that does not report a level exposes an unknown state."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {0: DaliGearData(level=None, device_types=(6,))}
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    assert light.is_on is None
    assert light.brightness is None


async def test_light_turn_on_clamps_to_max_level(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test the commanded level never exceeds the gear's configured max level."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {
        0: DaliGearData(level=0, min_level=1, max_level=200, device_types=(6,))
    }
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with patch.object(coordinator, "async_update_gear", new_callable=AsyncMock):
        await light.async_turn_on(brightness=255)
    assert isinstance(fake_dali_driver.sent[-1], DAPC)
    assert fake_dali_driver.sent[-1].power == 200


async def test_light_turn_on_transmission_error_raises_home_assistant_error(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a TransmissionError on turn-on is surfaced as a HomeAssistantError."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {0: DaliGearData(level=0, min_level=1, device_types=(6,))}
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with (
        patch.object(fake_dali_driver, "send", side_effect=TransmissionError(1)),
        pytest.raises(HomeAssistantError),
    ):
        await light.async_turn_on(brightness=255)


def test_dali_level_to_brightness_never_rounds_on_level_to_zero() -> None:
    """Test a nonzero on-level never maps to a brightness of 0.

    The logarithmic curve rounds the lowest on-levels toward 0; a gear that is
    on must still report at least brightness 1 so it does not read as off.
    """
    for level in range(1, 255):
        assert _dali_level_to_brightness(level, False) >= 1


@pytest.mark.parametrize(
    ("gear", "expected"),
    [
        (DaliGearData(device_types=(6,)), True),
        (DaliGearData(device_types=()), False),
    ],
    ids=["dt6", "non_led"],
)
def test_is_light_only_matches_led_gear(gear: DaliGearData, expected: bool) -> None:
    """Test only dimmable (DT6) gear become lights."""
    assert _is_light(gear) is expected


async def test_light_setup_adds_new_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fake_dali_driver: FakeDaliDriver,
) -> None:
    """Test the light platform creates entities and registers a listener."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dali.DriverLubaRs232",
        return_value=fake_dali_driver,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    entity_entries = [
        entity
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.domain == LIGHT_DOMAIN
    ]
    assert len(entity_entries) == 2
    assert {
        entity.unique_id.rsplit("_", maxsplit=1)[-1] for entity in entity_entries
    } == {"0", "2"}


@pytest.mark.parametrize("min_level", [1, 86, 96, 128, 200])
@pytest.mark.parametrize("linear_dimming", [False, True])
def test_brightness_level_round_trip_is_stable(
    min_level: int, linear_dimming: bool
) -> None:
    """Test set-then-read of a brightness settles to a fixed point.

    Reading the sent level back must reproduce a brightness that maps to the
    same level again, so the UI slider does not keep drifting after a command.
    """
    for brightness in range(1, 256):
        level = _brightness_to_dali_level(brightness, linear_dimming, min_level)
        assert min_level <= level <= 254
        read_back = _dali_level_to_brightness(level, linear_dimming)
        assert _brightness_to_dali_level(read_back, linear_dimming, min_level) == level


@pytest.mark.parametrize("min_level", [1, 86, 96, 128, 200])
@pytest.mark.parametrize("linear_dimming", [False, True])
def test_brightness_to_level_snaps_to_closest_readback(
    min_level: int, linear_dimming: bool
) -> None:
    """Test the chosen level reads back closer than any nearby level."""
    for brightness in range(1, 256):
        level = _brightness_to_dali_level(brightness, linear_dimming, min_level)
        chosen_error = abs(
            _dali_level_to_brightness(level, linear_dimming) - brightness
        )
        for other in range(max(min_level, level - 5), min(254, level + 5) + 1):
            other_error = abs(
                _dali_level_to_brightness(other, linear_dimming) - brightness
            )
            assert chosen_error <= other_error


async def test_light_turn_on_without_brightness_keeps_level(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test turning on without a brightness keeps the current dimmed level."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {
        0: DaliGearData(level=128, min_level=1, linear_dimming=True, device_types=(6,))
    }
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with patch.object(coordinator, "async_update_gear", new_callable=AsyncMock):
        await light.async_turn_on()

    assert isinstance(fake_dali_driver.sent[-1], DAPC)
    assert fake_dali_driver.sent[-1].power == _brightness_to_dali_level(128, True, 1)
    # Not the full-output level a missing brightness used to command.
    assert fake_dali_driver.sent[-1].power != _brightness_to_dali_level(255, True, 1)


async def test_light_turn_on_failure_raises_home_assistant_error(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test turn-on communication errors are surfaced."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {0: DaliGearData(level=128, device_types=(6,))}
    light = DaliLight(coordinator, entry.entry_id, entry.title, 0, set())

    with (
        patch.object(fake_dali_driver, "send", side_effect=OSError("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await light.async_turn_on()
