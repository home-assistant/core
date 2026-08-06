from unittest.mock import AsyncMock, patch

import pytest
from pytewke.error import PyTewkeCoapError, PyTewkeInvalidResponseError

from homeassistant.components.tewke.coordinator import _fetch_with_retries


async def test_fetch_with_retries_success():
    """Test _fetch_with_retries succeeds on first try."""
    mock_fn = AsyncMock(return_value="success")
    result = await _fetch_with_retries(mock_fn)
    assert result == "success"
    assert mock_fn.call_count == 1


async def test_fetch_with_retries_transient_error():
    """Test _fetch_with_retries succeeds after retries."""
    mock_fn = AsyncMock(side_effect=[PyTewkeCoapError("Timeout", 408), "success"])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _fetch_with_retries(mock_fn)

    assert result == "success"
    assert mock_fn.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


async def test_fetch_with_retries_exhausted():
    """Test _fetch_with_retries raises after exhausting retries."""
    mock_fn = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(PyTewkeCoapError):
            await _fetch_with_retries(mock_fn)

    assert mock_fn.call_count == 3
    assert mock_sleep.call_count == 2


async def test_fetch_with_retries_non_transient():
    """Test _fetch_with_retries fails immediately on non-transient error."""
    mock_fn = AsyncMock(side_effect=PyTewkeInvalidResponseError("Invalid"))

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(PyTewkeInvalidResponseError):
            await _fetch_with_retries(mock_fn)

    assert mock_fn.call_count == 1
    assert mock_sleep.call_count == 0


import logging
from unittest.mock import MagicMock

from homeassistant.components.tewke.coordinator import TewkeCoordinator
from homeassistant.core import HomeAssistant


async def test_coordinator_update_data_first_boot(
    hass: HomeAssistant, mock_config_entry, mock_tap
):
    """Test coordinator fetch data on first boot."""
    from homeassistant.components.tewke.data import TewkeData

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=MagicMock(),
        scenes={"scene1": {"name": "Mock Scene"}},
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
    assert data["scenes"] == {"scene1": {"name": "Mock Scene"}}
    assert data["scenes_all"] == {"scene1": {"name": "Mock Scene"}}
    assert data["targets"] == {}
    assert data["sensors"] is None

    assert mock_tap.get_scenes.call_count == 1
    assert mock_tap.get_targets.call_count == 1
    assert mock_tap.get_sensors.call_count == 1


async def test_coordinator_update_data_active_observe(
    hass: HomeAssistant, mock_config_entry, mock_tap
):
    """Test coordinator skips fetch if observe is active and data is populated."""
    from homeassistant.components.tewke.data import TewkeData

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=MagicMock(),
        scenes={},
        observe_active=True,
    )

    coordinator = TewkeCoordinator(
        hass,
        logging.getLogger(__name__),
        "test",
        mock_config_entry,
    )
    coordinator.data = {"scenes": {}}

    data = await coordinator._async_update_data()
    assert data == {"scenes": {}}
    assert mock_tap.get_scenes.call_count == 0
