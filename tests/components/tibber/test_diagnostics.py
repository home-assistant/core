"""Test the Tibber diagnostics."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import tibber

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import TibberRuntimeData
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .conftest import create_tibber_device
from .test_common import mock_get_homes

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_tibber_setup: MagicMock,
) -> None:
    """Test config entry diagnostics."""
    tibber_mock = mock_tibber_setup
    runtime = hass.data[DOMAIN]
    runtime.session = None
    tibber_mock.get_homes.return_value = []

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "homes": [],
    }

    tibber_mock.get_homes.side_effect = mock_get_homes

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "homes": [
            {
                "last_data_timestamp": "2016-01-01T12:48:57",
                "has_active_subscription": True,
                "has_real_time_consumption": False,
                "last_cons_data_timestamp": "2016-01-01T12:44:57",
                "country": "NO",
            }
        ],
    }


async def test_data_api_diagnostics_no_runtime(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test Data API diagnostics when runtime is not available."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="data-api",
    )
    config_entry.add_to_hass(hass)

    tibber_mock = MagicMock()
    tibber_mock.get_homes = MagicMock(return_value=[])
    runtime = TibberRuntimeData(session=None, tibber_connection=tibber_mock)
    hass.data[DOMAIN] = runtime

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result == {
        "homes": [],
    }


async def test_data_api_diagnostics_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test Data API diagnostics with successful device retrieval."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="data-api",
    )
    config_entry.add_to_hass(hass)

    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = "test-token"

    client = MagicMock()
    client.get_all_devices = AsyncMock(
        return_value={
            "device-1": create_tibber_device(
                device_id="device-1",
                name="Device 1",
                brand="Tibber",
                model="Test Model",
            ),
            "device-2": create_tibber_device(
                device_id="device-2",
                name="Device 2",
                brand="Tibber",
                model="Test Model",
            ),
        }
    )

    runtime = TibberRuntimeData(session=session, tibber_connection=MagicMock())
    with patch.object(
        TibberRuntimeData,
        "async_get_client",
        new_callable=AsyncMock,
        return_value=client,
    ):
        hass.data[DOMAIN] = runtime

        result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["error"] is None
    assert len(result["devices"]) == 2
    device_ids = {device["id"] for device in result["devices"]}
    assert device_ids == {"device-1", "device-2"}
    for device in result["devices"]:
        assert device["id"] in ("device-1", "device-2")
        assert device["brand"] == "Tibber"
        assert device["model"] == "Test Model"
        if device["id"] == "device-1":
            assert device["name"] == "Device 1"
        else:
            assert device["name"] == "Device 2"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (ConfigEntryAuthFailed("Auth failed"), "Authentication failed"),
        (TimeoutError(), "Timeout error"),
        (aiohttp.ClientError("Connection error"), "Client error"),
        (tibber.InvalidLoginError(401), "Invalid login"),
        (tibber.RetryableHttpExceptionError(503), "Retryable HTTP error (503)"),
        (tibber.FatalHttpExceptionError(404), "Fatal HTTP error (404)"),
    ],
)
async def test_data_api_diagnostics_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test Data API diagnostics with various exception scenarios."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="data-api",
    )
    config_entry.add_to_hass(hass)

    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = "test-token"

    client = MagicMock()
    client.get_all_devices = AsyncMock(side_effect=exception)

    runtime = TibberRuntimeData(session=session, tibber_connection=MagicMock())
    with patch.object(
        TibberRuntimeData,
        "async_get_client",
        new_callable=AsyncMock,
        return_value=client,
    ):
        hass.data[DOMAIN] = runtime

        result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["error"] == expected_error
    assert result["devices"] == []
