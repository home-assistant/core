"""Test the my-PV switch platform."""

from unittest.mock import AsyncMock, Mock, patch

from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TOGGLE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_my_pv_client")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a switch."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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
    assert state.state == "off"

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
    assert state.state == "off"


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
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
    assert state.state == "off"
