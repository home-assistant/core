"""Tests for lawn_mower module."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_integration
from .utils import make_complete_mower_list

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def setup_entity(hass: HomeAssistant):
    """Set up entity and config entry."""

    config_entry: MockConfigEntry = await setup_integration(hass)

    config_entry.add_to_hass(hass)
    token_decoded = load_fixture("token_decoded.json", DOMAIN)
    mowers = make_complete_mower_list()

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            name="AutomowerMockSession",
            model=AutomowerSession,
            data=mowers,
            register_data_callback=MagicMock(),
            unregister_data_callback=MagicMock(),
            connect=AsyncMock(),
            resume_schedule=AsyncMock(),
        ),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session",
        return_value=AsyncMock(),
    ), patch(
        "jwt.decode", return_value=token_decoded
    ), patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mowers,
    ) as mock_impl:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        mock_impl.assert_called_once()

    return config_entry

    # @pytest.mark.asyncio
    # async def test_lawn_mower_state(hass: HomeAssistant) -> None:
    #     """Test lawn_mower state."""
    #     await setup_entity(hass)
    #     # coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN]["automower_test"]
    #     # lawn_mower1 = AutomowerLawnMowerEntity(MWR_ONE_ID, coordinator)

    #     lawn_mower1 = hass.states.get("lawn_mower.test_mower_1")

    #     _LOGGER.debug("lawn_mower1:%s", lawn_mower1.as_dict())

    #     assert lawn_mower1.state == LawnMowerActivity.DOCKED
    #     assert lawn_mower1.state == LawnMowerActivity.PAUSED

    #     set_state(MowerStates.WAIT_POWER_UP)
    #     assert lawn_mower1.state == LawnMowerActivity.PAUSED
    #     set_state(MowerStates.IN_OPERATION)
    #     set_activity(MowerActivities.MOWING)
    #     assert lawn_mower1.state == LawnMowerActivity.MOWING

    #     set_activity(MowerActivities.LEAVING)
    #     assert lawn_mower1.state == LawnMowerActivity.MOWING

    #     set_activity(MowerActivities.GOING_HOME)
    #     assert lawn_mower1.state == LawnMowerActivity.MOWING

    #     set_state(MowerStates.RESTRICTED)
    #     set_activity(MowerActivities.PARKED_IN_CS)
    #     assert lawn_mower1.state == LawnMowerActivity.DOCKED

    #     set_activity(MowerActivities.CHARGING)
    #     assert lawn_mower1.state == LawnMowerActivity.DOCKED
    #     set_activity(MowerActivities.UNKNOWN)
    #     set_state(MowerStates.FATAL_ERROR)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.ERROR)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.ERROR_AT_POWER_UP)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.NOT_APPLICABLE)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.UNKNOWN)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.STOPPED)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_state(MowerStates.OFF)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_activity(MowerActivities.STOPPED_IN_GARDEN)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_activity(MowerActivities.UNKNOWN)
    #     assert lawn_mower1.state == LawnMowerActivity.ERROR

    #     set_activity(MowerActivities.NOT_APPLICABLE)
    # assert lawn_mower1.state == LawnMowerActivity.ERROR


@pytest.mark.asyncio
async def test_lawn_mower_commands(hass: HomeAssistant) -> None:
    """Test lawn_mower commands."""

    await setup_entity(hass)

    await hass.services.async_call(
        "lawn_mower",
        service="start_mowing",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )

    await hass.services.async_call(
        "lawn_mower",
        service="pause",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )

    await hass.services.async_call(
        "lawn_mower",
        service="dock",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )
