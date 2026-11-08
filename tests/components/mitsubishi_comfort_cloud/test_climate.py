"""Tests for Mitsubishi Comfort Cloud climate entities."""

from unittest.mock import AsyncMock, call

from freezegun.api import FrozenDateTimeFactory
from mitsubishi_comfort.exceptions import (
    AuthenticationError,
    CommandError,
    DeviceConnectionError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
)
from homeassistant.components.mitsubishi_comfort_cloud.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import MOCK_SERIAL

ENTITY_ID = "climate.living_room"


@pytest.mark.parametrize(
    ("units", "requested", "celsius", "step", "minimum", "maximum"),
    [
        pytest.param(US_CUSTOMARY_SYSTEM, 69, 21.0, 1.0, 61, 86, id="69F"),
        pytest.param(US_CUSTOMARY_SYSTEM, 70, 21.5, 1.0, 61, 86, id="70F"),
        pytest.param(US_CUSTOMARY_SYSTEM, 71, 22.0, 1.0, 61, 86, id="71F"),
        pytest.param(US_CUSTOMARY_SYSTEM, 72, 22.5, 1.0, 61, 86, id="72F"),
        pytest.param(US_CUSTOMARY_SYSTEM, 73, 23.0, 1.0, 61, 86, id="73F"),
        pytest.param(US_CUSTOMARY_SYSTEM, 74, 23.5, 1.0, 61, 86, id="74F"),
        pytest.param(METRIC_SYSTEM, 22.5, 22.5, 0.5, 16, 30, id="celsius"),
    ],
)
@pytest.mark.parametrize(("mode", "field"), [("cool", "spCool"), ("heat", "spHeat")])
async def test_app_setpoint_conversion(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    freezer: FrozenDateTimeFactory,
    units: UnitSystem,
    requested: float,
    celsius: float,
    step: float,
    minimum: float,
    maximum: float,
    mode: str,
    field: str,
) -> None:
    """App selections survive service conversion, optimistic state, and polling."""
    hass.config.units = units
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: requested},
        blocking=True,
    )
    mock_cloud_account.send_command.assert_awaited_once_with(
        MOCK_SERIAL, {field: celsius}
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == requested
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == step
    assert state.attributes[ATTR_MIN_TEMP] == minimum
    assert state.attributes[ATTR_MAX_TEMP] == maximum

    mock_cloud_account.get_device_details.return_value[field] = celsius
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == requested


@pytest.mark.parametrize("mode", ["auto", "autoCool", "autoHeat"])
async def test_fahrenheit_target_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mode: str,
) -> None:
    """Automatic stages retain both targets and the app's room temperature."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_cloud_account.get_device_details.return_value.update(
        {"operationMode": mode, "roomTemp": 22.0}
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_LOW: 71,
            ATTR_TARGET_TEMP_HIGH: 73,
        },
        blocking=True,
    )
    assert mock_cloud_account.send_command.await_args_list == [
        call(MOCK_SERIAL, {"spCool": 23.0}),
        call(MOCK_SERIAL, {"spHeat": 22.0}),
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 71
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 73
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 71

    mock_cloud_account.get_device_details.return_value.update(
        {"spHeat": 22.0, "spCool": 23.0}
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 71
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 73


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
            "set_fan_mode",
            {"fan_mode": "super_quiet"},
            {"fanSpeed": "superQuiet"},
            id="super-quiet-fan",
        ),
        pytest.param(
            "set_fan_mode",
            {"fan_mode": "super_powerful"},
            {"fanSpeed": "superPowerful"},
            id="super-powerful-fan",
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
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )
    mock_cloud_account.send_command.assert_awaited_once_with(MOCK_SERIAL, command)


@pytest.mark.parametrize(
    ("error", "reauth_steps", "message"),
    [
        pytest.param(CommandError("rejected"), [], "did not accept", id="rejected"),
        pytest.param(
            DeviceConnectionError("timeout"),
            [],
            "Error communicating with Living Room",
            id="timeout",
        ),
        pytest.param(
            AuthenticationError("expired"),
            ["reauth_confirm"],
            "did not accept",
            id="authentication",
        ),
    ],
)
async def test_cloud_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    error: Exception,
    reauth_steps: list[str],
    message: str,
) -> None:
    """Failed commands preserve state and only auth failures request reauth."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_cloud_account.send_command.side_effect = error
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": "heat"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "cool"
    assert [
        (flow["step_id"], flow["context"]["entry_id"])
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ] == [(step, mock_config_entry.entry_id) for step in reauth_steps]


async def test_cloud_poll_authentication_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Authentication failure during polling starts reauth without unloading."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_cloud_account.get_device_details.side_effect = AuthenticationError("expired")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
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
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
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
    before = hass.states.get(ENTITY_ID)
    mock_cloud_account.send_command.side_effect = DeviceConnectionError("offline")
    with pytest.raises(
        HomeAssistantError, match="Error communicating with Living Room"
    ) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )
    assert exc_info.value.__cause__ is mock_cloud_account.send_command.side_effect
    assert exc_info.value.translation_key == "communication_error"
    assert hass.states.get(ENTITY_ID) == before


@pytest.mark.parametrize(
    ("results", "expected_low", "expected_high", "message"),
    [
        pytest.param(
            [CommandError("rejected"), None],
            20.0,
            24.0,
            "did not accept",
            id="cool-fails",
        ),
        pytest.param(
            [None, CommandError("rejected")],
            21.0,
            26.0,
            "did not accept",
            id="heat-fails",
        ),
        pytest.param(
            [DeviceConnectionError("offline"), None],
            21.0,
            24.0,
            "Error communicating with Living Room",
            id="cool-connection-fails",
        ),
        pytest.param(
            [None, DeviceConnectionError("offline")],
            21.0,
            26.0,
            "Error communicating with Living Room",
            id="heat-connection-fails",
        ),
    ],
)
async def test_partial_temperature_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    results: list[CommandError | DeviceConnectionError | None],
    expected_low: float,
    expected_high: float,
    message: str,
) -> None:
    """Preserve an accepted setpoint when the other command is rejected."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = "auto"
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_cloud_account.send_command.side_effect = results
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "target_temp_low": 20,
                "target_temp_high": 26,
            },
            blocking=True,
        )
    state = hass.states.get(ENTITY_ID)
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
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": "heat"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == "heat"
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "cool"
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
    assert hass.states.get(ENTITY_ID) == snapshot


@pytest.mark.parametrize("mode", ["auto", "autoCool", "autoHeat"])
@pytest.mark.parametrize(
    ("auto_min", "auto_max", "low", "high"),
    [
        pytest.param(None, None, 16, 30, id="heat-cool-bounds"),
        pytest.param(10, 35, 10, 35, id="wider-auto-bounds"),
    ],
)
async def test_automatic_temperature_bounds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mode: str,
    auto_min: float | None,
    auto_max: float | None,
    low: float,
    high: float,
) -> None:
    """All automatic modes accept both setpoints at the supported boundaries."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    profile = mock_cloud_account.get_device_profile.return_value
    profile["minimumSetPoints"]["auto"] = auto_min
    profile["maximumSetPoints"]["auto"] = auto_max
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "target_temp_low": low,
            "target_temp_high": high,
        },
        blocking=True,
    )
    assert mock_cloud_account.send_command.await_args_list == [
        call(MOCK_SERIAL, {"spCool": high}),
        call(MOCK_SERIAL, {"spHeat": low}),
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["target_temp_low"] == low
    assert state.attributes["target_temp_high"] == high


@pytest.mark.parametrize(
    ("mode", "data", "commands", "expected_mode"),
    [
        pytest.param(
            "cool",
            {"hvac_mode": "heat", "temperature": 22},
            [{"operationMode": "heat"}, {"spHeat": 22}],
            "heat",
            id="cool-to-heat",
        ),
        pytest.param(
            "off",
            {"hvac_mode": "heat", "temperature": 22},
            [{"operationMode": "heat"}, {"spHeat": 22}],
            "heat",
            id="off-to-heat",
        ),
        pytest.param(
            "cool",
            {"hvac_mode": "heat", "temperature": 16},
            [{"operationMode": "heat"}, {"spHeat": 16}],
            "heat",
            id="cool-to-heat-minimum",
        ),
        pytest.param(
            "heat",
            {"hvac_mode": "cool", "temperature": 30},
            [{"operationMode": "cool"}, {"spCool": 30}],
            "cool",
            id="heat-to-cool-maximum",
        ),
        pytest.param(
            "off",
            {"hvac_mode": "heat_cool", "target_temp_low": 16, "target_temp_high": 30},
            [{"operationMode": "auto"}, {"spCool": 30}, {"spHeat": 16}],
            "heat_cool",
            id="off-to-auto-range",
        ),
    ],
)
async def test_combined_mode_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mode: str,
    data: dict[str, str | float],
    commands: list[dict[str, str | float]],
    expected_mode: str,
) -> None:
    """Apply the requested mode before choosing and sending its setpoints."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )
    assert mock_cloud_account.send_command.await_args_list == [
        call(MOCK_SERIAL, command) for command in commands
    ]
    assert hass.states.get(ENTITY_ID).state == expected_mode


@pytest.mark.parametrize(
    "hvac_mode",
    [
        pytest.param("auto", id="unmapped-mode"),
        pytest.param("heat", id="unsupported-device-mode"),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"temperature": 25}, id="single"),
        pytest.param({"target_temp_low": 20, "target_temp_high": 26}, id="range"),
    ],
)
async def test_unsupported_combined_mode_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    hvac_mode: str,
    data: dict[str, float],
) -> None:
    """Unsupported modes must fail before changing mode or setpoints."""
    mock_cloud_account.get_device_profile.return_value["hasModeHeat"] = False
    mock_cloud_account.get_device_profile.return_value["maximumSetPoints"].pop("heat")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = hass.states.get(ENTITY_ID)
    assert hvac_mode not in before.attributes["hvac_modes"]

    with pytest.raises(ServiceValidationError, match="is not valid"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": hvac_mode, **data},
            blocking=True,
        )
    mock_cloud_account.send_command.assert_not_awaited()
    assert hass.states.get(ENTITY_ID) == before


@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(CommandError("rejected"), "did not accept", id="rejected"),
        pytest.param(
            DeviceConnectionError("offline"),
            "Error communicating with Living Room",
            id="connection",
        ),
        pytest.param(
            AuthenticationError("expired"), "did not accept", id="authentication"
        ),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"hvac_mode": "heat", "temperature": 22}, id="single"),
        pytest.param(
            {"hvac_mode": "heat_cool", "target_temp_low": 20, "target_temp_high": 26},
            id="range",
        ),
    ],
)
async def test_failed_mode_change_stops_temperature_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    error: Exception,
    message: str,
    data: dict[str, str | float],
) -> None:
    """A failed mode command must not change any setpoints or optimistic state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = hass.states.get(ENTITY_ID)
    mock_cloud_account.send_command.side_effect = error

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )
    assert mock_cloud_account.send_command.await_count == 1
    assert "operationMode" in mock_cloud_account.send_command.await_args.args[1]
    assert hass.states.get(ENTITY_ID) == before


@pytest.mark.parametrize(
    ("minimums", "maximums", "expected_min", "expected_max"),
    [
        pytest.param({}, {}, 7, 35, id="unknown"),
        pytest.param({"heat": 16}, {"heat": 28}, 16, 28, id="heat-only"),
        pytest.param({"cool": 18}, {"cool": 30}, 18, 30, id="cool-only"),
        pytest.param({"auto": 10}, {"auto": 35}, 10, 35, id="auto-only"),
        pytest.param({"heat": 16}, {}, 16, 35, id="missing-maximum"),
        pytest.param({}, {"cool": 30}, 7, 30, id="missing-minimum"),
    ],
)
async def test_partial_temperature_bounds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    minimums: dict[str, float],
    maximums: dict[str, float],
    expected_min: float,
    expected_max: float,
) -> None:
    """Use available profile bounds, defaulting only when none are reported."""
    profile = mock_cloud_account.get_device_profile.return_value
    profile["minimumSetPoints"] = minimums
    profile["maximumSetPoints"] = maximums
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["min_temp"] == expected_min
    assert state.attributes["max_temp"] == expected_max


@pytest.mark.parametrize(
    ("mode", "temperature"),
    [
        pytest.param("heat", 30, id="above-heat-maximum"),
        pytest.param("cool", 16, id="below-cool-minimum"),
    ],
)
async def test_reject_invalid_mode_setpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mode: str,
    temperature: float,
) -> None:
    """The library still rejects invalid setpoints within the overall range."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = hass.states.get(ENTITY_ID)

    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, "temperature": temperature},
            blocking=True,
        )
    mock_cloud_account.send_command.assert_not_awaited()
    assert hass.states.get(ENTITY_ID) == before


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("off", HVACAction.OFF),
        ("auto", HVACAction.IDLE),
        ("autoCool", HVACAction.COOLING),
        ("autoHeat", HVACAction.HEATING),
        ("vent", HVACAction.FAN),
        ("cool", None),
        ("heat", None),
        ("dry", None),
        ("unknown", None),
        (None, None),
    ],
)
async def test_reported_hvac_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mode: str | None,
    expected: HVACAction | None,
) -> None:
    """Report observed stages without guessing compressor activity from mode."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = mode
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes.get(ATTR_HVAC_ACTION) == expected


async def test_hvac_action_waits_for_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Selecting a mode cannot manufacture an observed operating stage."""
    mock_cloud_account.get_device_details.return_value["operationMode"] = "off"
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": "heat_cool"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == "heat_cool"
    assert hass.states.get(ENTITY_ID).attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    mock_cloud_account.get_device_details.return_value["operationMode"] = "autoHeat"
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] is None


@pytest.mark.parametrize(
    ("units", "celsius", "expected"),
    [
        (US_CUSTOMARY_SYSTEM, 21.5, 70),
        (US_CUSTOMARY_SYSTEM, 22.0, 71),
        (US_CUSTOMARY_SYSTEM, 22.5, 72),
        (US_CUSTOMARY_SYSTEM, 23.0, 73),
        (US_CUSTOMARY_SYSTEM, 10.0, 50),
        (US_CUSTOMARY_SYSTEM, None, None),
        (METRIC_SYSTEM, 22.0, 22.0),
        (METRIC_SYSTEM, None, None),
    ],
)
async def test_app_room_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    units: UnitSystem,
    celsius: float | None,
    expected: float | None,
) -> None:
    """Cloud roomTemp uses Mitsubishi's display scale, including 22 C -> 71 F."""
    hass.config.units = units
    mock_cloud_account.get_device_details.return_value["roomTemp"] = celsius
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_CURRENT_TEMPERATURE] == expected


@pytest.mark.parametrize(
    ("attribute", "value", "label"),
    [
        ("fan_mode", "super_quiet", "Super quiet"),
        ("swing_mode", "midhorizontal", "Mid-horizontal"),
    ],
)
async def test_mode_translations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    attribute: str,
    value: str,
    label: str,
) -> None:
    """Custom protocol values have labels through the entity translation key."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(ENTITY_ID)
    translations = await async_get_translations(hass, "en", "entity", {DOMAIN})
    assert (
        translations[
            f"component.{DOMAIN}.entity.climate.{entry.translation_key}"
            f".state_attributes.{attribute}.state.{value}"
        ]
        == label
    )


@pytest.mark.parametrize(
    ("fan_mode", "raw"),
    [("super_quiet", "superQuiet"), ("super_powerful", "superPowerful")],
)
async def test_fan_mode_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    freezer: FrozenDateTimeFactory,
    fan_mode: str,
    raw: str,
) -> None:
    """Translated fan identifiers survive commands and subsequent polling."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, "fan_mode": fan_mode},
        blocking=True,
    )
    mock_cloud_account.send_command.assert_awaited_once_with(
        MOCK_SERIAL, {"fanSpeed": raw}
    )
    assert hass.states.get(ENTITY_ID).attributes["fan_mode"] == fan_mode

    mock_cloud_account.get_device_details.return_value["fanSpeed"] = raw
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["fan_mode"] == fan_mode
