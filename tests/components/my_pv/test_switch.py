"""Test the my-PV switch platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from my_pv.exceptions import (
    MyPVAuthenticationError,
    MyPVConnectionError,
    MyPVTooManyRequestsError,
)
import pytest
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

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def setup_configuration(setup_configuration: dict[str, Any]) -> dict[str, Any]:
    """Return a setup configuration where bstmode is a boolean (switch)."""
    return {**setup_configuration, "bstmode": {"type": "boolean"}}


@pytest.fixture
def setup_values(setup_values: dict[str, Any]) -> dict[str, Any]:
    """Return setup values with a boolean bstmode."""
    return {**setup_values, "bstmode": False}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a switch."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_water_heater_switch_no_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a switch for the water heater is created when there is no temperature sensor installed."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.my_pv_ac_elwa_2")
    assert state.state == STATE_ON


async def test_water_heater_switch_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test that no switch for the water heater is created when there is a temperature sensor installed."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = 30

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.my_pv_ac_elwa_2")
    assert state is None


@pytest.mark.parametrize(
    ("entity", "method", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", "turn_on", ()),
        ("switch.my_pv_ac_elwa_2_boost_mode", "set_setup_value", ("bstmode", True)),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test if a switch is unavailable when not connected."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None
        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_unavailable_setup_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a switch is unavailable when setup value is None."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.get_setup_value = Mock(return_value=None)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity", "method", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", "turn_on", ()),
        ("switch.my_pv_ac_elwa_2_boost_mode", "set_setup_value", ("bstmode", True)),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test turn on."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None
        mock_my_pv_client.is_on = False
        mock_my_pv_client.get_setup_value = Mock(return_value=False)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    client_method = getattr(mock_my_pv_client, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity,
        },
        blocking=True,
    )
    client_method.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("entity", "method", "expected_args"),
    [
        ("switch.my_pv_ac_elwa_2", "turn_off", ()),
        ("switch.my_pv_ac_elwa_2_boost_mode", "set_setup_value", ("bstmode", False)),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test turn off."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None
        mock_my_pv_client.is_on = True
        mock_my_pv_client.get_setup_value = Mock(return_value=True)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    client_method = getattr(mock_my_pv_client, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test toggle."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None
        mock_my_pv_client.is_on = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    entity: str,
    method: str,
    expected_args: tuple,
) -> None:
    """Test for HomeAssistantError when toggle method returns false."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None
        mock_my_pv_client.is_on = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    client_method = getattr(mock_my_pv_client, method)
    client_method.return_value = False

    with (
        pytest.raises(HomeAssistantError),
    ):
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.current_temperature = None

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    client_method = getattr(mock_my_pv_client, method)
    client_method.side_effect = error

    with (
        pytest.raises(expected_ha_error),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: entity},
            blocking=True,
        )
    client_method.assert_awaited_once_with(*expected_args)

    state = hass.states.get(entity)
    assert state.state == expected_state
