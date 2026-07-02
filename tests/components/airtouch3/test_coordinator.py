"""Test the AirTouch 3 coordinator."""

from enum import Enum
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, call, patch

from pyairtouch3 import AirTouchError
from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import ZoneStatus
import pytest

from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    AirTouch3Data,
    Airtouch3DataUpdateCoordinator,
    async_fetch_airtouch_data,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


class CommandType(Enum):
    """Test command enum."""

    SET_MODE = "set_mode"


def _zone(
    zone_id: int,
    name: str,
    desired_temperature: int,
    status: ZoneStatus,
    current_temperature: int | None = None,
) -> AirtouchZone:
    """Create a zone fixture."""
    zone = AirtouchZone(20)
    zone.id = zone_id
    zone.name = name
    zone.desired_temperature = desired_temperature
    zone.status = status
    if current_temperature is not None:
        sensor = Sensor()
        sensor.current_temperature = current_temperature
        sensor.is_available = True
        zone.sensor = sensor
    return zone


def _aircon() -> Aircon:
    """Create AirTouch data for coordinator tests."""
    aircon = Aircon(1)
    aircon.brand_id = 2
    aircon.status = True
    aircon.zones = [
        _zone(1, "Living", 20, ZoneStatus.ZONE_ON, 23),
        _zone(2, "Bedroom", 21, ZoneStatus.ZONE_OFF),
    ]
    return aircon


def _coordinator(hass: HomeAssistant) -> Airtouch3DataUpdateCoordinator:
    """Create a coordinator with data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = AirTouch3Data.from_aircon(_aircon())
    return coordinator


async def test_async_fetch_airtouch_data_success() -> None:
    """Test fetching AirTouch data delegates to pyairtouch3."""
    aircon = _aircon()
    fetch_aircon = AsyncMock(return_value=aircon)

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        result = await async_fetch_airtouch_data("1.1.1.1")

    assert result is aircon
    client_class.assert_called_once_with("1.1.1.1", 8899, logger=ANY)
    fetch_aircon.assert_awaited_once()


async def test_async_fetch_airtouch_data_error_raises_update_failed() -> None:
    """Test pyairtouch3 errors are surfaced as update failures."""
    fetch_aircon = AsyncMock(side_effect=AirTouchError("bad response"))

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")

    fetch_aircon.assert_awaited_once()


async def test_async_fetch_airtouch_data_missing_ac_id_raises_update_failed() -> None:
    """Test incomplete pyairtouch3 data is surfaced as an update failure."""
    aircon = _aircon()
    aircon.ac_id = None

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = AsyncMock(return_value=aircon)
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")


async def test_update_data_uses_parsed_response(hass: HomeAssistant) -> None:
    """Test coordinator refresh stores parsed AirTouch data."""
    coordinator = _coordinator(hass)
    parsed = _aircon()

    with patch(
        "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
        AsyncMock(return_value=parsed),
    ):
        result = await coordinator._async_update_data()

    assert result.aircon is parsed
    assert result.zones == {zone.id: zone for zone in parsed.zones}


async def test_send_command_normalizes_command_key(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test command type enum values are normalized before dispatch."""
    coordinator = _coordinator(hass)
    set_mode = AsyncMock()
    monkeypatch.setattr(coordinator._client, "set_mode", set_mode)

    await coordinator.send_command(cast(str, CommandType.SET_MODE), 1, 4)
    await coordinator.send_command(cast(str, 123), 1)

    set_mode.assert_awaited_once_with(1, 2, 4)


@pytest.mark.parametrize(
    ("command_type", "target_id", "value", "method_name", "expected_args"),
    [
        ("set_mode", 1, 4, "set_mode", (1, 2, 4)),
        ("set_fan_speed", 1, 3, "set_fan_speed", (1, 2, 3)),
        ("set_group_temperature", 1, -1, "adjust_zone_temperature", (1, -1)),
        ("toggle_zone", 1, None, "toggle_zone", (1,)),
    ],
)
async def test_send_command_delegates_to_pyairtouch3_client(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    target_id: int,
    value: int | None,
    method_name: str,
    expected_args: tuple[Any, ...],
) -> None:
    """Test commands delegate to the pyairtouch3 client."""
    coordinator = _coordinator(hass)
    method = AsyncMock()
    monkeypatch.setattr(coordinator._client, method_name, method)

    await coordinator.send_command(command_type, target_id, value)

    method.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("command_type", "initial_status", "expected_status"),
    [
        ("turn_on", False, True),
        ("turn_off", True, False),
    ],
)
async def test_send_command_sends_power_toggle(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    initial_status: bool,
    expected_status: bool,
) -> None:
    """Test AC power commands send only when a toggle is required."""
    coordinator = _coordinator(hass)
    coordinator.data.aircon.status = initial_status
    toggle_ac_power = AsyncMock()
    monkeypatch.setattr(coordinator._client, "toggle_ac_power", toggle_ac_power)

    await coordinator.send_command(command_type, 1)

    toggle_ac_power.assert_awaited_once_with(1)
    assert coordinator.data.aircon.status is expected_status


@pytest.mark.parametrize(
    ("command_type", "initial_status"),
    [
        ("turn_on", True),
        ("turn_off", False),
        ("unknown", True),
    ],
)
async def test_send_command_skips_unneeded_or_unknown_commands(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    initial_status: bool,
) -> None:
    """Test no command is sent when no protocol message is needed."""
    coordinator = _coordinator(hass)
    coordinator.data.aircon.status = initial_status
    toggle_ac_power = AsyncMock()
    monkeypatch.setattr(coordinator._client, "toggle_ac_power", toggle_ac_power)

    await coordinator.send_command(command_type, 1)

    toggle_ac_power.assert_not_called()


async def test_send_command_handles_write_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test command delivery handles pyairtouch3 write errors."""
    coordinator = _coordinator(hass)
    toggle_zone = AsyncMock(side_effect=AirTouchError("closed"))
    monkeypatch.setattr(coordinator._client, "toggle_zone", toggle_zone)

    await coordinator.send_command("toggle_zone", 1)

    toggle_zone.assert_awaited_once_with(1)


async def test_adjust_temperature_sends_step_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator temperature adjustment sends one command per step."""
    coordinator = _coordinator(hass)
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    await coordinator.adjust_temperature(1, 22)

    assert send_command.mock_calls == [
        call("set_group_temperature", 1, 1),
        call("set_group_temperature", 1, 1),
    ]


async def test_adjust_temperature_skips_missing_target(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator temperature adjustment skips unknown zones."""
    coordinator = _coordinator(hass)
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    await coordinator.adjust_temperature(99, 22)

    send_command.assert_not_called()
