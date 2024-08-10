"""Tests for the Mealie integration."""

from unittest.mock import AsyncMock

from aiomealie import About, MealieAuthenticationError, MealieConnectionError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.mealie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "field",
    [
        "get_about",
        "get_mealplans",
        "get_shopping_lists",
        "get_statistics",
    ],
)
@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (MealieConnectionError, ConfigEntryState.SETUP_RETRY),
        (MealieAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    field: str,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup failure."""
    getattr(mock_mealie_client, field).side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


@pytest.mark.parametrize(
    ("version"),
    [
        ("v1.0.0beta-5"),
        ("v1.0.0-RC2"),
        ("v0.1.0"),
    ],
)
async def test_setup_too_old(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    version,
) -> None:
    """Test setup of Mealie entry with too old version of Mealie."""
    mock_mealie_client.get_about.return_value = About(version=version)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_invalid(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup of Mealie entry with too old version of Mealie."""
    mock_mealie_client.get_about.return_value = About(version="nightly")

    await setup_integration(hass, mock_config_entry)

    assert (
        "It seems like you are using the nightly version of Mealie, nightly"
        " versions could have changes that stop this integration working" in caplog.text
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (MealieConnectionError, ConfigEntryState.SETUP_RETRY),
        (MealieAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_mealplan_initialization_failure(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test initialization failure."""
    mock_mealie_client.get_mealplans.side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (MealieConnectionError, ConfigEntryState.SETUP_RETRY),
        (MealieAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_shoppingitems_initialization_failure(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test initialization failure."""
    mock_mealie_client.get_shopping_items.side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
