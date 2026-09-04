"""Test Tewke coordinator."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytewke import Scene
from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidResponseError,
    PyTewkeObserveError,
)

from homeassistant.components.tewke.coordinator import (
    TewkeCoordinator,
    _fetch_with_retries,
)
from homeassistant.components.tewke.data import TewkeData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_fetch_with_retries_success() -> None:
    """Test _fetch_with_retries succeeds on first try."""
    mock_fn = AsyncMock(return_value="success")
    result = await _fetch_with_retries(mock_fn)
    assert result == "success"
    assert mock_fn.call_count == 1


async def test_fetch_with_retries_transient_error() -> None:
    """Test _fetch_with_retries succeeds after retries."""
    mock_fn = AsyncMock(side_effect=[PyTewkeCoapError("Timeout", 408), "success"])

    with patch(
        "homeassistant.components.tewke.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        result = await _fetch_with_retries(mock_fn)

    assert result == "success"
    assert mock_fn.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


async def test_fetch_with_retries_exhausted() -> None:
    """Test _fetch_with_retries raises after exhausting retries."""
    mock_fn = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))

    with (
        patch(
            "homeassistant.components.tewke.coordinator.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(PyTewkeCoapError),
    ):
        await _fetch_with_retries(mock_fn)

    assert mock_fn.call_count == 3
    assert mock_sleep.call_count == 2


async def test_fetch_with_retries_non_transient() -> None:
    """Test _fetch_with_retries fails immediately on non-transient error."""
    mock_fn = AsyncMock(side_effect=PyTewkeInvalidResponseError("Invalid"))

    with (
        patch(
            "homeassistant.components.tewke.coordinator.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(PyTewkeInvalidResponseError),
    ):
        await _fetch_with_retries(mock_fn)

    assert mock_fn.call_count == 1
    assert mock_sleep.call_count == 0


async def test_coordinator_update_data_first_boot(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test coordinator fetch data on first boot."""

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=MagicMock(),
        observe_active=False,
    )
    mock_tap.get_scenes.return_value = {"scene1": {"name": "Mock Scene"}}

    coordinator = TewkeCoordinator(
        hass,
        logging.getLogger(__name__),
        "test",
        mock_config_entry,
    )

    data = await coordinator._async_update_data()
    assert data["scenes"] == {"scene1": {"name": "Mock Scene"}}  # type: ignore[comparison-overlap]
    assert data["targets"] == {}
    assert data["sensors"] is None

    assert mock_tap.get_scenes.call_count == 1
    assert mock_tap.get_targets.call_count == 1
    assert mock_tap.get_sensors.call_count == 1


async def test_coordinator_update_data_active_observe(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test coordinator skips fetch if observe is active and data is populated."""

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=MagicMock(),
        observe_active=True,
    )

    coordinator = TewkeCoordinator(
        hass,
        logging.getLogger(__name__),
        "test",
        mock_config_entry,
    )
    coordinator.data = {"scenes": {}}  # type: ignore[typeddict-item]

    data = await coordinator._async_update_data()
    assert data == {"scenes": {}}  # type: ignore[comparison-overlap]
    assert mock_tap.get_scenes.call_count == 0


async def test_coordinator_new_scenes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test finding new scenes during polling."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    new_scene = Scene(id="99", name="New Scene", isActive=False, brightness=255)

    async def _get_scenes(*args, **kwargs):
        return {"99": new_scene}

    mock_tap.get_scenes.side_effect = _get_scenes

    mock_tap.observe.side_effect = PyTewkeObserveError
    mock_config_entry.runtime_data.observe_active = False

    data = await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert "99" in data["scenes"]
    assert data["scenes"]["99"].name == "New Scene"
