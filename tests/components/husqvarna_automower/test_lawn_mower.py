"""Tests for lawn_mower module."""
from copy import deepcopy
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.model import MowerActivities, MowerStates
from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import (
    AutomowerDataUpdateCoordinator,
)
from homeassistant.components.husqvarna_automower.lawn_mower import (
    AutomowerLawnMowerEntity,
)
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_integration
from .const import AUTOMOWER_SM_SESSION_DATA, MWR_ONE_ID
from .utils import make_complete_mower_list

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)
TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjVlZDU2ZDUzLTEyNWYtNDExZi04ZTFlLTNlNDRkMGVkOGJmOCJ9.eyJqdGkiOiI2MGYxNGQ1OS1iY2M4LTQwMzktYmMzOC0yNWRiMzc2MGQwNDciLCJpc3MiOiJodXNxdmFybmEiLCJyb2xlcyI6W10sImdyb3VwcyI6WyJhbWMiLCJkZXZlbG9wZXItcG9ydGFsIiwiZmQ3OGIzYTQtYTdmOS00Yzc2LWJlZjktYWE1YTUwNTgzMzgyIiwiZ2FyZGVuYS1teWFjY291bnQiLCJodXNxdmFybmEtY29ubmVjdCIsImh1c3F2YXJuYS1teXBhZ2VzIiwic21hcnRnYXJkZW4iXSwic2NvcGVzIjpbImlhbTpyZWFkIiwiYW1jOmFwaSJdLCJzY29wZSI6ImlhbTpyZWFkIGFtYzphcGkiLCJjbGllbnRfaWQiOiI0MzNlNWZkZi01MTI5LTQ1MmMteHh4eC1mYWRjZTMyMTMwNDIiLCJjdXN0b21lcl9pZCI6IjQ3NTU5OTc3MjA0NTh4eHh4IiwidXNlciI6eyJmaXJzdF9uYW1lIjoiSm9obiIsImxhc3RfbmFtZSI6IkRvZSIsImN1c3RvbV9hdHRyaWJ1dGVzIjp7ImhjX2NvdW50cnkiOiJERSJ9LCJjdXN0b21lcl9pZCI6IjQ3NTU5OTc3MjA0NTh4eHh4In0sImlhdCI6MTY5NzY2Njk0NywiZXhwIjoxNjk3NzUzMzQ3LCJzdWIiOiI1YTkzMTQxZS01NWE3LTQ3OWYtOTZlMi04YTYzMTg4YzA1NGYifQ.1O3FOoWHaWpo - PrW88097ai6nsUGlK2NWyqIDLkUl1BTatQoFhIA1nKmCthf6A9CAYeoPS4c8CBhqqLj - 5VrJXfNc7pFZ1nAw69pT33Ku7_S9QqonPf_JRvWX8 - A7sTCKXEkCTso6v_jbmiePK6C9_psClJx_PUgFFOoNaROZhSsAlq9Gftvzs9UTcd2UO9ohsku_Kpx480C0QCKRjm4LTrFTBpgijRPc3F0BnyfgW8rT3Trl290f3CyEzLk8k9bgGA0qDlAanKuNNKK1j7hwRsiq_28A7bWJzlLc6Wgrq8Pc2CnnMada_eXavkTu - VzB - q8_PGFkLyeG16CR - NXlox9mEB6NxTn5stYSMUkiTApAfgCwLuj4c_WCXnxUZn0VdnsswvaIZON3bTSOMATXLG8PFUyDOcDxHBV4LEDyTVspo - QblanTTBLFWMTfWIWApBmRO9OkiJrcq9g7T8hKNNImeN4skk2vIZVXkCq_cEOdVAG4099b1V8zXCBgtDc"
token_decoded = {
    "jti": "60f14d59-bcc8-4039-bc38-25db3760d047",
    "iss": "husqvarna",
    "roles": [],
    "groups": [
        "amc",
        "developer-portal",
        "fd78b3a4-a7f9-4c76-bef9-aa5a50583382",
        "gardena-myaccount",
        "husqvarna-connect",
        "husqvarna-mypages",
        "smartgarden",
    ],
    "scopes": ["iam:read", "amc:api"],
    "scope": "iam:read amc:api",
    "client_id": "433e5fdf-5129-452c-xxxx-fadce3213042",
    "customer_id": "4755997720458xxxx",
    "user": {
        "first_name": "John",
        "last_name": "Doe",
        "custom_attributes": {"hc_country": "DE"},
        "customer_id": "4755997720458xxxx",
    },
    "iat": 1697666947,
    "exp": 1697753347,
    "sub": "5a93141e-55a7-479f-96e2-8a63188c054f",
}


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def setup_entity(hass: HomeAssistant):
    """Set up entity and config entry."""

    config_entry: MockConfigEntry = await setup_integration(hass)

    config_entry.add_to_hass(hass)
    load_fixture("jwt.js", DOMAIN)
    deepcopy(AUTOMOWER_SM_SESSION_DATA)
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


@pytest.mark.asyncio
async def test_lawn_mower_state(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    await setup_entity(hass)
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN]["automower_test"]
    lawn_mower1 = AutomowerLawnMowerEntity(MWR_ONE_ID, coordinator)

    def set_state(state: str):
        """Set new state."""
        coordinator.data[MWR_ONE_ID].mower.state = state

    def set_activity(activity: str):
        """Set new state."""
        coordinator.data[MWR_ONE_ID].mower.activity = activity

    assert lawn_mower1._attr_unique_id == f"{MWR_ONE_ID}_lawn_mower"
    set_state(MowerStates.PAUSED)
    assert lawn_mower1.activity == LawnMowerActivity.PAUSED

    set_state(MowerStates.WAIT_POWER_UP)
    assert lawn_mower1.state == LawnMowerActivity.PAUSED
    set_state(MowerStates.IN_OPERATION)
    set_activity(MowerActivities.MOWING)
    assert lawn_mower1.state == LawnMowerActivity.MOWING

    set_activity(MowerActivities.LEAVING)
    assert lawn_mower1.state == LawnMowerActivity.MOWING

    set_activity(MowerActivities.GOING_HOME)
    assert lawn_mower1.state == LawnMowerActivity.MOWING

    set_state(MowerStates.RESTRICTED)
    set_activity(MowerActivities.PARKED_IN_CS)
    assert lawn_mower1.state == LawnMowerActivity.DOCKED

    set_activity(MowerActivities.CHARGING)
    assert lawn_mower1.state == LawnMowerActivity.DOCKED
    set_activity(MowerActivities.UNKNOWN)
    set_state(MowerStates.FATAL_ERROR)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.ERROR)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.ERROR_AT_POWER_UP)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.NOT_APPLICABLE)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.UNKNOWN)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.STOPPED)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_state(MowerStates.OFF)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_activity(MowerActivities.STOPPED_IN_GARDEN)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_activity(MowerActivities.UNKNOWN)
    assert lawn_mower1.state == LawnMowerActivity.ERROR

    set_activity(MowerActivities.NOT_APPLICABLE)
    assert lawn_mower1.state == LawnMowerActivity.ERROR


# @pytest.mark.asyncio
# async def test_lawn_mower_commands(hass: HomeAssistant) -> None:
#     """Test lawn_mower commands."""

#     mower = make_single_mower_data()
#     await setup_entity(hass)
#     _LOGGER.debug("SETUP ERFOLGT")
#     _LOGGER.debug(hass.data[DOMAIN]["automower_test"])
#     coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN]["automower_test"]
#     _LOGGER.debug("coordinator:.data%s", coordinator.data)
#     for mower_id in coordinator.data:
#         lawn_mower = AutomowerLawnMowerEntity(mower_id, coordinator)
#     assert lawn_mower._attr_unique_id == f"{MWR_ONE_ID}_lawn_mower"

#     # Start
#     # Success
#     await lawn_mower.async_start_mowing()
#     coordinator.api.resume_schedule.assert_awaited_once_with(MWR_ONE_ID)

#     # Pause
#     # Success
#     await lawn_mower.async_pause()
#     coordinator.api.pause_mowing.assert_awaited_once_with(MWR_ONE_ID)

#     # Stop
#     # Success
#     await lawn_mower.async_dock()
#     coordinator.api.park_until_next_schedule.assert_awaited_once_with(MWR_ONE_ID)
