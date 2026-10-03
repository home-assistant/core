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
    assert state.state is STATE_ON


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a switch is unavailable when not connected."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting value."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.get_setup_value = Mock(return_value=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "switch.my_pv_ac_elwa_2_boost_mode",
        },
        blocking=True,
    )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting value."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.get_setup_value = Mock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "switch.my_pv_ac_elwa_2_boost_mode",
        },
        blocking=True,
    )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", False)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting value."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: "switch.my_pv_ac_elwa_2_boost_mode",
        },
        blocking=True,
    )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when set_setup_value returns false."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.set_setup_value = AsyncMock(return_value=False)

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {
                ATTR_ENTITY_ID: "switch.my_pv_ac_elwa_2_boost_mode",
            },
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", True)

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
        (MyPVTooManyRequestsError(), HomeAssistantError),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when set_setup_value raises error."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.set_setup_value = AsyncMock(side_effect=error)

    with (
        pytest.raises(expected_ha_error),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: "switch.my_pv_ac_elwa_2_boost_mode"},
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", True)

    state = hass.states.get("switch.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_OFF
