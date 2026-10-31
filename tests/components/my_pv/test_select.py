"""Test the my-PV select platform."""

from unittest.mock import AsyncMock, Mock, patch

from my_pv.exceptions import (
    MyPVAuthenticationError,
    MyPVConnectionError,
    MyPVTooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of the select platform."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a select is unavailable when not connected."""
    mock_my_pv_client.connected = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_UNAVAILABLE


async def test_select_unavailable_setup_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a select is unavailable when setup value is None."""
    mock_my_pv_client.get_setup_value = Mock(return_value=None)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == STATE_UNAVAILABLE


async def test_select_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == "0"

    mock_my_pv_client.get_setup_value = Mock(return_value="1")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_pv_ac_elwa_2_boost_mode",
            ATTR_OPTION: "1",
        },
        blocking=True,
    )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", "1")

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == "1"


async def test_select_select_option_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when set_setup_value returns false."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.set_setup_value.return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.my_pv_ac_elwa_2_boost_mode",
                ATTR_OPTION: "1",
            },
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", "1")

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == "0"


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
        (MyPVTooManyRequestsError(), HomeAssistantError),
    ],
)
async def test_select_select_option_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when set_setup_value raises error."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.set_setup_value.side_effect = error

    with pytest.raises(expected_ha_error):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_pv_ac_elwa_2_boost_mode", ATTR_OPTION: "1"},
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bstmode", "1")

    state = hass.states.get("select.my_pv_ac_elwa_2_boost_mode")
    assert state.state == "0"
