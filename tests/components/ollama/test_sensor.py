"""Tests for the Ollama sensor platform."""

from unittest.mock import AsyncMock, patch

from httpx import ConnectError
import ollama
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ollama.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@patch("homeassistant.components.ollama.PLATFORMS", (Platform.SENSOR,))
@patch(
    "ollama.AsyncClient.list",
    new=AsyncMock(
        return_value=ollama.ListResponse(
            models=[{"model": "zeta"}, {"model": "alpha"}, {"model": "beta"}]
        )
    ),
)
@patch(
    "ollama.AsyncClient.ps",
    new=AsyncMock(
        return_value=ollama.ProcessResponse(
            models=[
                {"model": "zeta", "size": 8_000_000_000, "size_vram": 6_000_000_000},
                {"model": "alpha", "size": 4_000_000_000, "size_vram": 1_000_000_000},
            ]
        )
    ),
)
async def test_model_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the model sensors."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "side_effect",
    [
        ConnectError("Failed to connect"),
        ConnectionError("Failed to connect"),
        ollama.ResponseError("Failed to connect"),
        TimeoutError(),
    ],
)
@patch("ollama.AsyncClient.list", return_value=ollama.ListResponse(models=[]))
@patch("ollama.AsyncClient.ps")
async def test_loaded_model_sensors_unavailable(
    mock_ps: AsyncMock,
    mock_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
    side_effect: Exception,
) -> None:
    """Test only loaded model sensors are unavailable when ps fails."""
    mock_ps.side_effect = side_effect
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    loaded_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_loaded_models"
    )
    installed_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_installed_models"
    )
    assert loaded_entity_id is not None
    assert installed_entity_id is not None
    loaded_state = hass.states.get(loaded_entity_id)
    installed_state = hass.states.get(installed_entity_id)
    assert loaded_state.state == STATE_UNAVAILABLE
    assert installed_state.state == "0"


@patch("ollama.AsyncClient.list", return_value=ollama.ListResponse(models=[{}, {}]))
@patch(
    "ollama.AsyncClient.ps",
    side_effect=[ConnectionError, ollama.ProcessResponse(models=[{}])],
)
async def test_model_sensors_recover(
    mock_ps: AsyncMock,
    mock_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
) -> None:
    """Test the model sensors recover after a connection failure."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    loaded_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_loaded_models"
    )
    installed_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_installed_models"
    )
    assert loaded_entity_id is not None
    assert installed_entity_id is not None
    await async_update_entity(hass, loaded_entity_id)

    loaded_state = hass.states.get(loaded_entity_id)
    installed_state = hass.states.get(installed_entity_id)
    assert loaded_state.state == "1"
    assert installed_state.state == "2"
    assert mock_ps.await_count == 2
    assert mock_list.await_count == 2
