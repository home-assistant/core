"""Test the my-PV switch platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from my_pv.exceptions import (
    MyPVAuthenticationError,
    MyPVConnectionError,
    MyPVTooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.fixture
def setup_configuration(setup_configuration: dict[str, Any]) -> dict[str, Any]:
    """Return a setup configuration where bstmode is a boolean (switch)."""
    return {**setup_configuration, "bstmode": {"type": "boolean"}}


@pytest.fixture
def setup_values(setup_values: dict[str, Any]) -> dict[str, Any]:
    """Return setup values with a boolean bstmode."""
    return {**setup_values, "bstmode": False}


@pytest.fixture
def mock_my_pv_client(mock_my_pv_client: AsyncMock) -> AsyncMock:
    """Return a client without a temperature sensor, so the water heater switch exists."""
    mock_my_pv_client.current_temperature = None
    return mock_my_pv_client


async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a switch."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_water_heater_switch_no_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a switch for the water heater is created when there is no temperature sensor installed."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.my_pv_ac_elwa_2")
    assert state.state == STATE_ON


async def test_water_heater_switch_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test that no switch for the water heater is created when there is a temperature sensor installed."""
    mock_my_pv_client.current_temperature = 30

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.my_pv_ac_elwa_2")
    assert state is None


@pytest.mark.parametrize(
    "entity",
    ["switch.my_pv_ac_elwa_2", "switch.my_pv_ac_elwa_2_boost_mode"],
)
async def test_switch_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
) -> None:
    """Test if a switch is unavailable when not connected."""
    mock_my_pv_client.connected = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity)
    assert state.state == STATE_UNAVAILABLE


async def test_switch_unavailable_setup_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a switch is unavailable when setup value is None."""
    mock_my_pv_client.get_setup_value = Mock(return_value=None)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity", "initial_state", "method", "service", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", False, "turn_on", SERVICE_TURN_ON, ()),
        (
            "switch.my_pv_ac_elwa_2_boost_mode",
            False,
            "set_setup_value",
            SERVICE_TURN_ON,
            ("bstmode", True),
        ),
        ("switch.my_pv_ac_elwa_2", True, "turn_off", SERVICE_TURN_OFF, ()),
        (
            "switch.my_pv_ac_elwa_2_boost_mode",
            True,
            "set_setup_value",
            SERVICE_TURN_OFF,
            ("bstmode", False),
        ),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    initial_state: bool,
    method: str,
    service: str,
    expected_args: tuple,
) -> None:
    """Test turn on/off."""
    mock_my_pv_client.is_on = initial_state
    mock_my_pv_client.get_setup_value.side_effect = None
    mock_my_pv_client.get_setup_value.return_value = initial_state

    await setup_integration(hass, mock_config_entry)

    client_method = getattr(mock_my_pv_client, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity,
        },
        blocking=True,
    )
    client_method.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("entity", "method", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", "turn_on", ()),
        ("switch.my_pv_ac_elwa_2_boost_mode", "set_setup_value", ("bstmode", True)),
    ],
)
async def test_switch_toggle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test toggle."""
    mock_my_pv_client.is_on = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity)
    assert state.state == STATE_OFF

    client_method = getattr(mock_my_pv_client, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: entity,
        },
        blocking=True,
    )
    client_method.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("entity", "method", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", "turn_on", ()),
        ("switch.my_pv_ac_elwa_2_boost_mode", "set_setup_value", ("bstmode", True)),
    ],
)
async def test_switch_toggle_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test for HomeAssistantError when toggle method returns false."""
    mock_my_pv_client.is_on = False

    await setup_integration(hass, mock_config_entry)

    client_method = getattr(mock_my_pv_client, method)
    client_method.return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {
                ATTR_ENTITY_ID: entity,
            },
            blocking=True,
        )
    client_method.assert_awaited_once_with(*expected_args)

    state = hass.states.get(entity)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    (
        "entity",
        "method",
        "expected_args",
        "error",
        "expected_ha_error",
        "expected_state",
    ),
    [
        (
            "switch.my_pv_ac_elwa_2",
            "turn_off",
            (),
            MyPVConnectionError(),
            HomeAssistantError,
            STATE_ON,
        ),
        (
            "switch.my_pv_ac_elwa_2",
            "turn_off",
            (),
            MyPVAuthenticationError(),
            ConfigEntryAuthFailed,
            STATE_ON,
        ),
        (
            "switch.my_pv_ac_elwa_2",
            "turn_off",
            (),
            MyPVTooManyRequestsError(),
            HomeAssistantError,
            STATE_ON,
        ),
        (
            "switch.my_pv_ac_elwa_2_boost_mode",
            "set_setup_value",
            ("bstmode", True),
            MyPVConnectionError(),
            HomeAssistantError,
            STATE_OFF,
        ),
        (
            "switch.my_pv_ac_elwa_2_boost_mode",
            "set_setup_value",
            ("bstmode", True),
            MyPVAuthenticationError(),
            ConfigEntryAuthFailed,
            STATE_OFF,
        ),
        (
            "switch.my_pv_ac_elwa_2_boost_mode",
            "set_setup_value",
            ("bstmode", True),
            MyPVTooManyRequestsError(),
            HomeAssistantError,
            STATE_OFF,
        ),
    ],
)
async def test_switch_toggle_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
    expected_state: str,
) -> None:
    """Test for HomeAssistantError when method raises error."""
    await setup_integration(hass, mock_config_entry)

    client_method = getattr(mock_my_pv_client, method)
    client_method.side_effect = error

    with pytest.raises(expected_ha_error):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: entity},
            blocking=True,
        )
    client_method.assert_awaited_once_with(*expected_args)

    state = hass.states.get(entity)
    assert state.state == expected_state
