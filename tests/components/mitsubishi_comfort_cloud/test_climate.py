"""Tests for Mitsubishi Comfort Cloud climate entities."""

from unittest.mock import AsyncMock, call

from freezegun.api import FrozenDateTimeFactory
from mitsubishi_comfort.exceptions import (
    AuthenticationError,
    CommandError,
    DeviceConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.mitsubishi_comfort_cloud.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("service", "data", "command"),
    [
        pytest.param(
            "set_hvac_mode", {"hvac_mode": "heat"}, {"operationMode": "heat"}, id="mode"
        ),
        pytest.param(
            "set_temperature", {"temperature": 25}, {"spCool": 25.0}, id="temperature"
        ),
        pytest.param(
            "set_fan_mode", {"fan_mode": "auto"}, {"fanSpeed": "auto"}, id="fan"
        ),
        pytest.param(
            "set_swing_mode",
            {"swing_mode": "swing"},
            {"airDirection": "swing"},
            id="vane",
        ),
        pytest.param("turn_off", {}, {"operationMode": "off"}, id="off"),
    ],
)
async def test_cloud_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    service: str,
    data: dict[str, str | float],
    command: dict[str, str | float],
) -> None:
    """Home Assistant actions use cloud field names without local credentials."""
    mock_cloud_account.get_device_profile.return_value["hasVaneSwing"] = True
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.living_room", **data},
        blocking=True,
    )
    mock_cloud_account.send_command.assert_awaited_once_with(MOCK_SERIAL, command)


@pytest.mark.parametrize(
    ("error", "reauth_steps"),
    [
        pytest.param(CommandError("rejected"), [], id="rejected"),
        pytest.param(DeviceConnectionError("timeout"), [], id="timeout"),
        pytest.param(
            AuthenticationError("expired"), ["reauth_confirm"], id="authentication"
        ),
    ],
)
async def test_cloud_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    error: Exception,
    reauth_steps: list[str],
) -> None:
    """Failed commands preserve state and only auth failures request reauth."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_cloud_account.send_command.side_effect = error
    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {ATTR_ENTITY_ID: "climate.living_room", "hvac_mode": "heat"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room").state == "cool"
    assert [
        (flow["step_id"], flow["context"]["entry_id"])
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ] == [(step, mock_config_entry.entry_id) for step in reauth_steps]


async def test_cloud_poll_authentication_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Authentication failure during polling starts reauth without unloading."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_cloud_account.get_device_details.side_effect = AuthenticationError("expired")
    await mock_config_entry.runtime_data[MOCK_SERIAL].async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("climate.living_room").state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("mode", "data", "commands"),
    [
        pytest.param("heat", {"temperature": 22}, [{"spHeat": 22.0}], id="heat"),
        pytest.param(
            "auto",
            {"target_temp_low": 20, "target_temp_high": 26},
            [{"spCool": 26.0}, {"spHeat": 20.0}],
            id="range",
        ),
    ],
)
async def test_temperature_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mode: str,
    data: dict[str, float],
    commands: list[dict[str, float]],
) -> None:
    """Temperature actions use the cloud setpoints for the active mode."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: "climate.living_room", **data},
        blocking=True,
    )
    assert mock_cloud_account.send_command.await_args_list == [
        call(MOCK_SERIAL, command) for command in commands
    ]


@pytest.mark.parametrize(
    ("service", "data", "mode"),
    [
        pytest.param("set_temperature", {"temperature": 25}, "cool", id="cool"),
        pytest.param("set_temperature", {"temperature": 20}, "heat", id="heat"),
        pytest.param("set_fan_mode", {"fan_mode": "auto"}, "cool", id="fan"),
        pytest.param("set_swing_mode", {"swing_mode": "auto"}, "cool", id="vane"),
    ],
)
async def test_action_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    service: str,
    data: dict[str, str | float],
    mode: str,
) -> None:
    """Cloud failures surface as action errors without optimistic state changes."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = hass.states.get("climate.living_room")
    mock_cloud_account.send_command.side_effect = DeviceConnectionError("offline")
    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "climate.living_room", **data},
            blocking=True,
        )
    assert hass.states.get("climate.living_room") == before


@pytest.mark.parametrize(
    ("results", "expected_low", "expected_high"),
    [
        pytest.param([CommandError("rejected"), None], 20.0, 24.0, id="cool-fails"),
        pytest.param([None, CommandError("rejected")], 21.0, 26.0, id="heat-fails"),
    ],
)
async def test_partial_temperature_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    results: list[CommandError | None],
    expected_low: float,
    expected_high: float,
) -> None:
    """Preserve an accepted setpoint when the other command is rejected."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = "auto"
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_cloud_account.send_command.side_effect = results
    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {
                ATTR_ENTITY_ID: "climate.living_room",
                "target_temp_low": 20,
                "target_temp_high": 26,
            },
            blocking=True,
        )
    state = hass.states.get("climate.living_room")
    assert state.attributes["target_temp_low"] == expected_low
    assert state.attributes["target_temp_high"] == expected_high


async def test_poll_replaces_optimistic_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The scheduled poll replaces an accepted command with reported state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: "climate.living_room", "hvac_mode": "heat"},
        blocking=True,
    )
    assert hass.states.get("climate.living_room").state == "heat"
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room").state == "cool"
    assert mock_cloud_account.get_device_details.await_count == 2


@pytest.mark.parametrize("mode", ["off", "heat", "auto", "dry"])
async def test_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    snapshot: SnapshotAssertion,
    mode: str,
) -> None:
    """Report cloud capabilities, ranges, and action without inferring activity."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room") == snapshot
