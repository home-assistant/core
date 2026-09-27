"""Test the my-PV number platform."""

from unittest.mock import AsyncMock, Mock, patch

from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_my_pv_client")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of the number platform."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a number is unavailable when not connected."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == STATE_UNAVAILABLE


async def test_number_unavailable_setup_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a number is unavailable when setup value is None."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.get_setup_value = Mock(return_value=None)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == STATE_UNAVAILABLE


async def test_number_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting value."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == "55.0"

    mock_my_pv_client.get_setup_value = Mock(return_value=70.0)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.my_pv_ac_elwa_2_boost_target_temperature",
            ATTR_VALUE: 70.0,
        },
        blocking=True,
    )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bsttemp", 70.0)

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == "70.0"


async def test_number_set_value_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when set_setup_value returns false."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.set_setup_value = AsyncMock(return_value=False)

    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.my_pv_ac_elwa_2_boost_target_temperature",
                ATTR_VALUE: 70,
            },
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bsttemp", 70)

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == "55.0"


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
    ],
)
async def test_number_set_value_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when set_setup_value raises error."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.set_setup_value.side_effect = error

    with (
        pytest.raises(expected_ha_error),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.my_pv_ac_elwa_2_boost_target_temperature",
                ATTR_VALUE: 70,
            },
            blocking=True,
        )
    mock_my_pv_client.set_setup_value.assert_awaited_once_with("bsttemp", 70)

    state = hass.states.get("number.my_pv_ac_elwa_2_boost_target_temperature")
    assert state.state == "55.0"
