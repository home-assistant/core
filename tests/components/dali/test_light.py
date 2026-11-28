"""Test the Tridonic DALI light platform."""

from collections.abc import Generator
from unittest.mock import patch

from dali.exceptions import TransmissionError
from dali.gear.general import DAPC
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dali.const import DOMAIN
from homeassistant.components.dali.coordinator import (
    DaliGearData,
    _brightness_to_dali_level,
    _dali_level_to_brightness,
)
from homeassistant.components.dali.light import _is_light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDaliDriver

# The fake bus has linear DT6 gear at address 0 (minimum level 86), a DT1
# emergency gear at 1 and logarithmic DT6 gear at 2.
LINEAR_GEAR = 0
LOGARITHMIC_GEAR = 2


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the DALI config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JDALITESTENTRY0000000000",
        data={CONF_DEVICE: "/dev/ttyACM0"},
        title="USB-DALI2",
    )


@pytest.fixture
def mock_driver(fake_dali_driver: FakeDaliDriver) -> Generator[FakeDaliDriver]:
    """Make the integration use the fake DALI driver."""
    with patch(
        "homeassistant.components.dali.DriverLubaRs232",
        return_value=fake_dali_driver,
    ):
        yield fake_dali_driver


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the DALI config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry, address: int
) -> str:
    """Return the light entity ID of a short address."""
    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, DOMAIN, f"{entry.entry_id}_{address}"
    )
    assert entity_id is not None
    return entity_id


def _sent_dapc(driver: FakeDaliDriver) -> list[DAPC]:
    """Return the DAPC frames sent to the bus."""
    return [command for command in driver.sent if isinstance(command, DAPC)]


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test only DT6 gear become light entities."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("brightness", "expected_level"),
    [
        # Full brightness must never send DALI's 255 mask value.
        (255, 254),
        # A level below the gear's minimum is clamped up to it.
        (1, 86),
        (128, _brightness_to_dali_level(128, True, 86)),
    ],
)
async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
    brightness: int,
    expected_level: int,
) -> None:
    """Test turning on with a brightness sends the matching arc-power level."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LINEAR_GEAR)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    assert [command.power for command in _sent_dapc(mock_driver)] == [expected_level]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == _dali_level_to_brightness(
        expected_level, True
    )


async def test_turn_on_clamps_to_max_level(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test the commanded level never exceeds the gear's configured max level."""
    mock_driver.max_levels[LINEAR_GEAR] = 200
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LINEAR_GEAR)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )

    assert [command.power for command in _sent_dapc(mock_driver)] == [200]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == _dali_level_to_brightness(200, True)


async def test_turn_on_already_on_keeps_level(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test turning on an already-on light without a brightness sends nothing.

    A raw logarithmic level of 50 reads back as brightness 1, which maps back to
    raw level 1; re-sending it would dim the light.
    """
    mock_driver.levels[LOGARITHMIC_GEAR] = 50
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LOGARITHMIC_GEAR)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 1

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert _sent_dapc(mock_driver) == []
    assert mock_driver.levels[LOGARITHMIC_GEAR] == 50
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 1


async def test_turn_on_from_off_goes_full(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test turning on an off light without a brightness commands full output."""
    mock_driver.levels[LOGARITHMIC_GEAR] = 0
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LOGARITHMIC_GEAR)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert [command.power for command in _sent_dapc(mock_driver)] == [254]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


async def test_turn_on_after_external_switch_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test turning on works when another controller switched off between polls."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LOGARITHMIC_GEAR)
    # Another DALI controller switches the gear off; the poll has not seen it.
    mock_driver.levels[LOGARITHMIC_GEAR] = 0
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert [command.power for command in _sent_dapc(mock_driver)] == [254]
    assert mock_driver.levels[LOGARITHMIC_GEAR] == 254
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


async def test_turn_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test turning off sends arc-power level 0."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LINEAR_GEAR)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert [command.power for command in _sent_dapc(mock_driver)] == [0]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_unknown_level(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
) -> None:
    """Test a gear answering with the mask value exposes an unknown state."""
    mock_driver.levels[LINEAR_GEAR] = 255
    await _setup(hass, mock_config_entry)

    state = hass.states.get(_entity_id(entity_registry, mock_config_entry, LINEAR_GEAR))
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 255}),
        # Without a brightness, the level query before the command fails.
        (SERVICE_TURN_ON, {}),
        (SERVICE_TURN_OFF, {}),
    ],
    ids=["turn_on_brightness", "turn_on", "turn_off"],
)
@pytest.mark.parametrize(
    "error",
    [OSError("serial failure"), TimeoutError, TransmissionError(1)],
    ids=["os_error", "timeout", "transmission_error"],
)
async def test_command_failure_raises_home_assistant_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_driver: FakeDaliDriver,
    service: str,
    service_data: dict[str, int],
    error: Exception,
) -> None:
    """Test DALI communication errors are surfaced as Home Assistant errors."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(entity_registry, mock_config_entry, LINEAR_GEAR)

    with (
        patch.object(mock_driver, "send", side_effect=error),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"


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
