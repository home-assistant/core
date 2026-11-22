"""Test init of Nettigo Air Monitor integration."""

from unittest.mock import MagicMock

from aiohttp.client_exceptions import ClientError
from nettigo_air_monitor import ApiError, AuthFailedError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.nam.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("mock_nam_client")
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "11.03"


@pytest.mark.parametrize("exc", [ApiError("API Error"), ClientError, TimeoutError])
async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam: MagicMock,
    exc: Exception | type[Exception],
) -> None:
    """Test for setup failure if the connection to the device fails."""
    mock_nam.create.side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nam: MagicMock
) -> None:
    """Test for setup failure if the auth fails."""
    mock_nam.create.side_effect = AuthFailedError("Authorization has failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("mock_nam_client")
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("mock_nam_client")
async def test_remove_air_quality_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test remove air_quality entities from registry."""
    entity_registry.async_get_or_create(
        AIR_QUALITY_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-sds011",
        suggested_object_id="nettigo_air_monitor_sds011",
        disabled_by=None,
    )

    entity_registry.async_get_or_create(
        AIR_QUALITY_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-sps30",
        suggested_object_id="nettigo_air_monitor_sps30",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("air_quality.nettigo_air_monitor_sds011")
    assert entry is None

    entry = entity_registry.async_get("air_quality.nettigo_air_monitor_sps30")
    assert entry is None
