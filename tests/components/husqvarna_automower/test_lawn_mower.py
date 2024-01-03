"""Tests for lawn_mower module."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.model import MowerAttributes, MowerList
from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower import DOMAIN
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_integration
from .utils import make_mower_list

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

_LOGGER = logging.getLogger(__name__)

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def setup_entity(hass: HomeAssistant, mowers):
    """Set up entity and config entry."""

    config_entry: MockConfigEntry = await setup_integration(hass)

    config_entry.add_to_hass(hass)
    token_decoded = load_fixture("token_decoded.json", DOMAIN)
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
    ), patch("jwt.decode", return_value=token_decoded), patch(
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
async def test_lawn_mower_docked(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    mower = load_json_value_fixture("mower.json", DOMAIN)
    mowers: MowerList = make_mower_list(mower)
    await setup_entity(hass, mowers)
    lawn_mower1 = hass.states.get("lawn_mower.test_mower_1")
    assert lawn_mower1.state == LawnMowerActivity.DOCKED


@pytest.mark.asyncio
async def test_lawn_mower_paused(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    mower = load_json_value_fixture("mower.json", DOMAIN)
    mowers: MowerList = make_mower_list(mower)
    mower_data: MowerAttributes = mowers[TEST_MOWER_ID]
    mower_data.mower.state = "PAUSED"
    await setup_entity(hass, mowers)
    lawn_mower1 = hass.states.get("lawn_mower.test_mower_1")
    assert lawn_mower1.state == LawnMowerActivity.PAUSED


@pytest.mark.asyncio
async def test_lawn_mower_mowing(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    mower = load_json_value_fixture("mower.json", DOMAIN)
    mowers: MowerList = make_mower_list(mower)
    mower_data: MowerAttributes = mowers[TEST_MOWER_ID]
    mower_data.mower.activity = "MOWING"
    await setup_entity(hass, mowers)
    lawn_mower1 = hass.states.get("lawn_mower.test_mower_1")
    assert lawn_mower1.state == LawnMowerActivity.MOWING


@pytest.mark.asyncio
async def test_lawn_mower_error(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    mower = load_json_value_fixture("mower.json", DOMAIN)
    mowers: MowerList = make_mower_list(mower)
    mower_data: MowerAttributes = mowers[TEST_MOWER_ID]
    mower_data.mower.activity = "NOT_APPLICABLE"
    mower_data.mower.state = "ERROR"
    await setup_entity(hass, mowers)
    lawn_mower1 = hass.states.get("lawn_mower.test_mower_1")
    assert lawn_mower1.state == LawnMowerActivity.ERROR


@pytest.mark.asyncio
async def test_lawn_mower_commands(hass: HomeAssistant) -> None:
    """Test lawn_mower commands."""

    mower = load_json_value_fixture("mower.json", DOMAIN)
    mowers = make_mower_list(mower)
    await setup_entity(hass, mowers)

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
