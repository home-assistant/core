"""Test the Avea light platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.avea.const import DOMAIN
from homeassistant.components.avea.light import AveaLight
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DATA_INSTANCES, async_update_entity

from . import AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bulb() -> MagicMock:
    """Return a mocked Avea bulb."""
    bulb = MagicMock()
    bulb.connect.return_value = True
    bulb.get_name.return_value = "Bedroom"
    bulb.get_brightness.return_value = 0
    bulb.get_rgb.return_value = (0, 0, 0)
    return bulb


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom",
        unique_id=AVEA_DISCOVERY_INFO.address,
        data={CONF_ADDRESS: AVEA_DISCOVERY_INFO.address},
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_bulb: MagicMock
) -> AsyncGenerator[MagicMock]:
    """Set up the integration."""
    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch(
            "homeassistant.components.avea.light.bluetooth.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.avea.avea.Bulb", return_value=mock_bulb),
    ):
        mock_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_bulb


async def test_init_state(hass: HomeAssistant, setup_integration: MagicMock) -> None:
    """Test the initial state."""
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]
    assert state.attributes[ATTR_COLOR_MODE] is None


async def test_turn_on_and_off(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test turning the light on and off."""
    bulb = setup_integration

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(4095)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(2056)

    bulb.set_rgb.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_HS_COLOR: (0, 100)},
        blocking=True,
    )
    bulb.set_rgb.assert_called_with(255, 0, 0)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(0)


async def test_turn_on_with_zero_brightness(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test turning the light on with zero brightness keeps it off."""
    bulb = setup_integration

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 0},
        blocking=True,
    )

    bulb.set_brightness.assert_called_with(0)
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_COLOR_MODE] is None


async def test_update_state(hass: HomeAssistant, setup_integration: MagicMock) -> None:
    """Test updating the entity state."""
    bulb = setup_integration
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (255, 0, 0)

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert state.attributes[ATTR_HS_COLOR] == (
        pytest.approx(0.0),
        pytest.approx(100.0),
    )


async def test_update_unavailable(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test the entity becomes unavailable on connection failure."""
    bulb = setup_integration
    bulb.connect.return_value = False
    bulb.close.reset_mock()

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    bulb.close.assert_called_once()


async def test_update_unavailable_on_invalid_brightness(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test the entity becomes unavailable on invalid brightness data."""
    bulb = setup_integration
    bulb.get_brightness.return_value = None

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_update_unavailable_on_invalid_rgb(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test the entity becomes unavailable on invalid RGB data."""
    bulb = setup_integration
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (255, 0)

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("service", ["turn_on", "turn_off"])
async def test_failed_connect_command_still_closes_bulb(
    hass: HomeAssistant,
    setup_integration: MagicMock,
    service: str,
) -> None:
    """Test a failed command still closes the bulb."""
    bulb = setup_integration
    bulb.connect.return_value = False
    bulb.close.reset_mock()

    with pytest.raises(ConnectionError):
        await hass.services.async_call(
            "light",
            service,
            {ATTR_ENTITY_ID: "light.bedroom"},
            blocking=True,
        )

    bulb.close.assert_called_once()


async def test_update_succeeds_when_close_raises(
    hass: HomeAssistant, setup_integration: MagicMock
) -> None:
    """Test cleanup errors after update do not mask successful reads."""
    bulb = setup_integration
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (255, 0, 0)
    bulb.close.side_effect = RuntimeError

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("service", "service_data", "expected_state"),
    [
        ("turn_on", {}, STATE_ON),
        ("turn_off", {}, STATE_OFF),
    ],
)
async def test_command_succeeds_when_close_raises(
    hass: HomeAssistant,
    setup_integration: MagicMock,
    service: str,
    service_data: dict[str, str],
    expected_state: str,
) -> None:
    """Test cleanup errors after commands do not mask success."""
    bulb = setup_integration
    bulb.close.side_effect = RuntimeError

    await hass.services.async_call(
        "light",
        service,
        {ATTR_ENTITY_ID: "light.bedroom", **service_data},
        blocking=True,
    )

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [("turn_on", STATE_ON), ("turn_off", STATE_OFF)],
)
async def test_command_restores_availability(
    hass: HomeAssistant,
    setup_integration: MagicMock,
    service: str,
    expected_state: str,
) -> None:
    """Test a successful command restores availability."""
    bulb = setup_integration
    bulb.connect.return_value = False

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    bulb.connect.return_value = True
    entity_comp = hass.data[DATA_INSTANCES]["light"]
    entity: AveaLight | None = entity_comp.get_entity("light.bedroom")
    assert entity is not None

    if service == "turn_on":
        await entity.async_turn_on()
    else:
        await entity.async_turn_off()
    entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == expected_state


async def test_remove_entry_closes_bulb(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    setup_integration: MagicMock,
) -> None:
    """Test removing the entry closes the bulb."""
    bulb = setup_integration
    bulb.close.reset_mock()

    await hass.config_entries.async_remove(mock_entry.entry_id)

    bulb.close.assert_called_once()
