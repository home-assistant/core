"""Test the pjlink media player platform."""

from datetime import timedelta
import socket
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pypjlink
from pypjlink import MUTE_AUDIO
from pypjlink.projector import ProjectorError
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import media_player
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import setup_pjlink_entry


@pytest.fixture(name="projector_from_address")
def projector_from_address():
    """Create pjlink Projector mock."""

    with patch("pypjlink.Projector.from_address") as from_address:
        constructor = create_autospec(pypjlink.Projector)
        constructor.__enter__.return_value = constructor
        from_address.return_value = constructor
        yield from_address


@pytest.fixture(name="mocked_projector")
def mocked_projector(projector_from_address: MagicMock) -> MagicMock:
    """Create pjlink Projector instance mock."""

    instance = projector_from_address.return_value

    instance.get_name.return_value = "Test"
    instance.get_power.return_value = "on"
    instance.get_mute.return_value = [0, True]
    instance.get_input.return_value = [0, 1]
    instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )

    instance.__enter__.return_value = instance

    return instance


@pytest.mark.parametrize("side_effect", [socket.timeout, OSError])
async def test_offline_initialization(
    projector_from_address: MagicMock, hass: HomeAssistant, side_effect: type[Exception]
) -> None:
    """Test initialization of a device that is offline."""

    projector_from_address.side_effect = side_effect

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_initialization(
    projector_from_address: MagicMock, hass: HomeAssistant
) -> None:
    """Test a device that is available."""

    mocked_instance = projector_from_address.return_value

    mocked_instance.get_name.return_value = "Test"
    mocked_instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )
    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    assert "source_list" in state.attributes
    source_list = state.attributes["source_list"]

    assert set(source_list) == {"HDMI 1", "HDMI 2", "VGA 1"}
    assert state.attributes["device_class"] == "projector"


@pytest.mark.parametrize("power_state", ["on", "warm-up"])
async def test_on_state_init(
    mocked_projector: MagicMock, hass: HomeAssistant, power_state: str
) -> None:
    """Test a device that is available."""

    mocked_projector.get_power.return_value = power_state
    mocked_projector.get_input.return_value = ("HDMI", 1)

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"

    assert state.attributes["source"] == "HDMI 1"


async def test_api_error(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test invalid api responses."""

    mocked_projector.get_power.side_effect = KeyError("OK")

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"


async def test_update_unavailable(
    projector_from_address: MagicMock, hass: HomeAssistant
) -> None:
    """Test update to a device that is unavailable."""

    mocked_instance = projector_from_address.return_value

    mocked_instance.get_name.return_value = "Test"
    mocked_instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    projector_from_address.side_effect = socket.timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_unavailable_time(
    mocked_projector: MagicMock, hass: HomeAssistant
) -> None:
    """Test unavailable time projector error."""

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"
    assert state.attributes["source"] is not None
    assert state.attributes["is_volume_muted"] is not False

    mocked_projector.get_power.side_effect = ProjectorError("unavailable time")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "off"
    assert "source" not in state.attributes
    assert "is_volume_muted" not in state.attributes


async def test_turn_off(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test turning off beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_off",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mocked_projector.set_power.assert_called_with("off")


async def test_turn_on(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test turning on beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_on",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mocked_projector.set_power.assert_called_with("on")


async def test_mute(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test muting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": True},
        blocking=True,
    )

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, True)


async def test_unmute(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test unmuting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": False},
        blocking=True,
    )

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, False)


async def test_select_source(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test selecting source."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="select_source",
        service_data={ATTR_ENTITY_ID: "media_player.test", "source": "VGA 1"},
        blocking=True,
    )

    mocked_projector.set_input.assert_called_with("VGA", 1)


_ERROR = ProjectorError("projector error")


@pytest.mark.parametrize(
    ("service", "service_data", "method_name"),
    [
        pytest.param("turn_off", {}, "set_power", id="turn_off"),
        pytest.param("turn_on", {}, "set_power", id="turn_on"),
        pytest.param(
            "volume_mute", {"is_volume_muted": True}, "set_mute", id="volume_mute"
        ),
        pytest.param(
            "select_source", {"source": "VGA 1"}, "set_input", id="select_source"
        ),
    ],
)
async def test_service_command_error_is_home_assistant_error(
    mocked_projector: MagicMock,
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, Any],
    method_name: str,
) -> None:
    """Projector failures during a service command surface as HomeAssistantError."""

    getattr(mocked_projector, method_name).side_effect = _ERROR

    await setup_pjlink_entry(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            media_player.DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.test", **service_data},
            blocking=True,
        )


async def test_service_error_when_projector_unreachable_is_home_assistant_error(
    mocked_projector: MagicMock,
    projector_from_address: MagicMock,
    hass: HomeAssistant,
) -> None:
    """A command on an unreachable projector surfaces as HomeAssistantError."""

    await setup_pjlink_entry(hass)

    projector_from_address.side_effect = socket.timeout

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            media_player.DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: "media_player.test"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "socket_error", [TimeoutError, OSError], ids=["timeout", "os_error"]
)
async def test_service_socket_error_during_command_is_home_assistant_error(
    mocked_projector: MagicMock,
    hass: HomeAssistant,
    socket_error: type[Exception],
) -> None:
    """A socket error raised by the command itself surfaces as HomeAssistantError."""

    mocked_projector.set_power.side_effect = socket_error

    await setup_pjlink_entry(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            media_player.DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: "media_player.test"},
            blocking=True,
        )
