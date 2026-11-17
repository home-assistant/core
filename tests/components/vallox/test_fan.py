"""Tests for Vallox fan platform."""

from unittest.mock import AsyncMock, _Call, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from vallox_websocket_api import (
    MetricValue,
    Profile,
    ValloxApiException,
    ValloxInvalidInputException,
)

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    METRICS_PROFILE_AUTO,
    METRICS_PROFILE_AWAY,
    METRICS_PROFILE_BOOST,
    METRICS_PROFILE_EXTRA,
    METRICS_PROFILE_FIREPLACE,
    METRICS_PROFILE_HOME,
    METRICS_PROFILE_UNKNOWN,
    METRICS_UNIT_OFF,
    METRICS_UNIT_ON,
    setup_integration,
)

FAN_ENTITY_ID = "fan.vallox"


@pytest.mark.usefixtures("mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the fan entity."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param(METRICS_UNIT_ON, STATE_ON, id="on"),
        pytest.param(METRICS_UNIT_OFF, STATE_OFF, id="off"),
    ],
)
async def test_fan_state(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    expected_state: str,
) -> None:
    """Test fan on/off state."""
    mock_vallox_client.fetch_metric_data.assert_called_once()
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_preset", "expected_percentage"),
    [
        # The fan speeds come from metrics.json: Home 30, Away 10 and Boost 80.
        pytest.param(METRICS_PROFILE_HOME, "home", 30, id="home"),
        pytest.param(METRICS_PROFILE_AWAY, "away", 10, id="away"),
        pytest.param(METRICS_PROFILE_BOOST, "boost", 80, id="boost"),
        pytest.param(METRICS_PROFILE_FIREPLACE, "fireplace", None, id="fireplace"),
        pytest.param(METRICS_PROFILE_EXTRA, "extra", None, id="extra"),
        pytest.param(METRICS_PROFILE_AUTO, "auto", None, id="auto"),
        pytest.param(METRICS_PROFILE_UNKNOWN, None, None, id="unknown"),
    ],
)
async def test_fan_profile(
    hass: HomeAssistant,
    expected_preset: str | None,
    expected_percentage: int | None,
) -> None:
    """Test the preset mode and fan speed of each profile."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [{"A_CYC_HOME_SPEED_SETTING": None}])
async def test_fan_speed_missing(hass: HomeAssistant) -> None:
    """Test a fan speed the unit does not report."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PERCENTAGE] is None
    assert state.attributes["fan_speed_home"] is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [{"A_CYC_MODE": None}])
async def test_fan_mode_missing(hass: HomeAssistant) -> None:
    """Test the fan when the unit does not report whether it is on."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "metrics", "expected_called_with"),
    [
        pytest.param(SERVICE_TURN_ON, METRICS_UNIT_OFF, METRICS_UNIT_ON, id="turn_on"),
        pytest.param(
            SERVICE_TURN_OFF, METRICS_UNIT_ON, METRICS_UNIT_OFF, id="turn_off"
        ),
        # The unit is already in the requested state according to the last poll.
        # It may have changed since, so check that the command is sent regardless.
        pytest.param(
            SERVICE_TURN_ON, METRICS_UNIT_ON, METRICS_UNIT_ON, id="turn_on_when_on"
        ),
        pytest.param(
            SERVICE_TURN_OFF, METRICS_UNIT_OFF, METRICS_UNIT_OFF, id="turn_off_when_off"
        ),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service: str,
    expected_called_with: dict[str, MetricValue],
) -> None:
    """Test turn on/off."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )

    mock_vallox_client.set_values.assert_called_once_with(expected_called_with)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "metrics"),
    [
        pytest.param(SERVICE_TURN_ON, METRICS_UNIT_OFF, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, METRICS_UNIT_ON, id="turn_off"),
    ],
)
async def test_turn_on_off_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock, service: str
) -> None:
    """Test turn on/off when the unit returns an error."""
    mock_vallox_client.set_values.side_effect = ValloxApiException("Fake failure")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "service_data", "expected_calls"),
    [
        pytest.param(
            METRICS_UNIT_OFF,
            {ATTR_PERCENTAGE: 15, ATTR_PRESET_MODE: "away"},
            [
                call.set_fan_speed(Profile.AWAY, 15),
                call.set_profile(Profile.AWAY),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="preset_and_percentage_unit_off",
        ),
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PERCENTAGE: 15, ATTR_PRESET_MODE: "away"},
            [
                call.set_fan_speed(Profile.AWAY, 15),
                call.set_profile(Profile.AWAY),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="preset_and_percentage_unit_on",
        ),
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PRESET_MODE: "away"},
            [
                call.set_profile(Profile.AWAY),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="preset_only",
        ),
        # The unit is already on and in Home according to the last poll. It may
        # have changed since, so check that the preset and power-on are sent
        # regardless.
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PRESET_MODE: "home"},
            [
                call.set_profile(Profile.HOME),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="active_preset",
        ),
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PERCENTAGE: 40},
            [
                call.set_fan_speed(Profile.HOME, 40),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="percentage_only",
        ),
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PERCENTAGE: 0},
            [
                call.set_values(METRICS_UNIT_OFF),
                call.fetch_metric_data(),
            ],
            id="zero_percentage",
        ),
        pytest.param(
            METRICS_UNIT_ON,
            {ATTR_PERCENTAGE: 0, ATTR_PRESET_MODE: "away"},
            [
                call.set_values(METRICS_UNIT_OFF),
                call.fetch_metric_data(),
            ],
            id="zero_percentage_with_preset",
        ),
        pytest.param(
            METRICS_UNIT_OFF,
            {ATTR_PERCENTAGE: 0},
            [
                call.set_values(METRICS_UNIT_OFF),
                call.fetch_metric_data(),
            ],
            id="zero_percentage_unit_off",
        ),
    ],
)
async def test_turn_on_with_parameters(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service_data: dict[str, int | str],
    expected_calls: list[_Call],
) -> None:
    """Test turn on with a preset mode, a percentage, or both."""
    # Forget the fetch at setup, so only the calls of the service remain.
    mock_vallox_client.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID} | service_data,
        blocking=True,
    )

    # One list over all methods also pins the order, and the refresh at the end.
    assert mock_vallox_client.method_calls == expected_calls


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [METRICS_UNIT_OFF])
@pytest.mark.parametrize(
    ("failing_method", "expected_calls"),
    [
        pytest.param(
            "set_fan_speed",
            [call.set_fan_speed(Profile.AWAY, 15)],
            id="speed",
        ),
        pytest.param(
            "set_profile",
            [
                call.set_fan_speed(Profile.AWAY, 15),
                call.set_profile(Profile.AWAY),
                call.fetch_metric_data(),
            ],
            id="preset",
        ),
        pytest.param(
            "set_values",
            [
                call.set_fan_speed(Profile.AWAY, 15),
                call.set_profile(Profile.AWAY),
                call.set_values(METRICS_UNIT_ON),
                call.fetch_metric_data(),
            ],
            id="power",
        ),
    ],
)
async def test_turn_on_exception(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    failing_method: str,
    expected_calls: list[_Call],
) -> None:
    """Test turn on when one of its commands returns an error."""
    mock_vallox_client.reset_mock()
    getattr(mock_vallox_client, failing_method).side_effect = ValloxApiException(
        "Fake failure"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: FAN_ENTITY_ID,
                ATTR_PERCENTAGE: 15,
                ATTR_PRESET_MODE: "away",
            },
            blocking=True,
        )

    # Refreshed only if a command before the failing one went through.
    assert mock_vallox_client.method_calls == expected_calls


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [METRICS_UNIT_OFF])
async def test_turn_on_unsupported_profile(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test turn on with a speed for a preset that has no fan speed setting."""
    mock_vallox_client.reset_mock()
    mock_vallox_client.set_fan_speed.side_effect = ValloxInvalidInputException(
        "Fan speed is not settable for profile"
    )

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: FAN_ENTITY_ID,
                ATTR_PERCENTAGE: 40,
                ATTR_PRESET_MODE: "fireplace",
            },
            blocking=True,
        )
    assert exc.value.translation_key == "preset_without_fan_speed"
    assert exc.value.translation_placeholders == {"preset_mode": "fireplace"}

    # The library rejects the speed before sending, so the unit is left as it was.
    assert mock_vallox_client.method_calls == [
        call.set_fan_speed(Profile.FIREPLACE, 40)
    ]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset", "metrics", "expected_profile"),
    [
        pytest.param("home", METRICS_PROFILE_AWAY, Profile.HOME, id="home"),
        pytest.param("away", METRICS_PROFILE_HOME, Profile.AWAY, id="away"),
        pytest.param("boost", METRICS_PROFILE_HOME, Profile.BOOST, id="boost"),
        pytest.param(
            "fireplace", METRICS_PROFILE_HOME, Profile.FIREPLACE, id="fireplace"
        ),
        pytest.param("extra", METRICS_PROFILE_HOME, Profile.EXTRA, id="extra"),
        pytest.param("auto", METRICS_PROFILE_HOME, Profile.AUTO, id="auto"),
        # The preset is already active according to the last poll. The unit may
        # have changed since, for example when its Boost timer ran out, so check
        # that the preset is sent regardless.
        pytest.param("home", METRICS_PROFILE_HOME, Profile.HOME, id="active_home"),
        pytest.param("boost", METRICS_PROFILE_BOOST, Profile.BOOST, id="active_boost"),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    preset: str,
    expected_profile: Profile,
) -> None:
    """Test set preset mode."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    mock_vallox_client.set_profile.assert_called_once_with(expected_profile)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
async def test_set_invalid_preset_mode(hass: HomeAssistant) -> None:
    """Test set an invalid preset mode."""
    with pytest.raises(NotValidPresetModeError) as exc:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "Invalid"},
            blocking=True,
        )
    assert exc.value.translation_key == "not_valid_preset_mode"


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test set preset mode when the unit returns an error."""
    mock_vallox_client.set_profile.side_effect = ValloxApiException("Fake exception")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "away"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    (
        "metrics",
        "percentage",
        "expected_set_fan_speed_calls",
        "expected_set_values_calls",
    ),
    [
        pytest.param(METRICS_PROFILE_HOME, 40, [call(Profile.HOME, 40)], [], id="home"),
        pytest.param(METRICS_PROFILE_AWAY, 30, [call(Profile.AWAY, 30)], [], id="away"),
        pytest.param(
            METRICS_PROFILE_BOOST, 60, [call(Profile.BOOST, 60)], [], id="boost"
        ),
        pytest.param(
            METRICS_PROFILE_HOME, 0, [], [call(METRICS_UNIT_OFF)], id="turn_off"
        ),
    ],
)
async def test_set_percentage(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    percentage: int,
    expected_set_fan_speed_calls: list[_Call],
    expected_set_values_calls: list[_Call],
) -> None:
    """Test set fan speed percentage."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert (
        mock_vallox_client.set_fan_speed.call_args_list == expected_set_fan_speed_calls
    )
    assert mock_vallox_client.set_values.call_args_list == expected_set_values_calls


@pytest.mark.usefixtures("init_integration")
async def test_set_percentage_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test set fan speed percentage when the unit returns an error."""
    mock_vallox_client.set_fan_speed.side_effect = ValloxApiException("Fake failure")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 5},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [METRICS_PROFILE_FIREPLACE])
async def test_set_percentage_unsupported_profile(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test setting the fan speed in a profile that has no fan speed setting."""
    mock_vallox_client.set_fan_speed.side_effect = ValloxInvalidInputException(
        "Fan speed is not settable for profile"
    )

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 40},
            blocking=True,
        )
    assert exc.value.translation_key == "preset_without_fan_speed"
    assert exc.value.translation_placeholders == {"preset_mode": "fireplace"}

    mock_vallox_client.set_fan_speed.assert_called_once_with(Profile.FIREPLACE, 40)
