"""Test the Tibber diagnostics."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import tibber

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import TibberDataAPIRuntimeData
from homeassistant.components.tibber.const import (
    API_TYPE_DATA_API,
    API_TYPE_GRAPHQL,
    CONF_API_TYPE,
    DOMAIN,
)
from homeassistant.components.tibber.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.setup import async_setup_component

from .conftest import create_tibber_device
from .test_common import mock_get_homes

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    with patch(
        "tibber.Tibber.update_info",
        return_value=None,
    ):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    with patch(
        "tibber.Tibber.get_homes",
        return_value=[],
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_type": API_TYPE_GRAPHQL,
        "homes": [],
    }

    with patch(
        "tibber.Tibber.get_homes",
        side_effect=mock_get_homes,
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_type": API_TYPE_GRAPHQL,
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
        data={CONF_API_TYPE: API_TYPE_DATA_API},
        unique_id="data-api",
    )
    config_entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result == {
        "api_type": API_TYPE_DATA_API,
        "devices": [],
    }


async def test_data_api_diagnostics_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test Data API diagnostics with successful device retrieval."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TYPE: API_TYPE_DATA_API},
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

    runtime = TibberDataAPIRuntimeData(session=session)
    with patch.object(
        TibberDataAPIRuntimeData,
        "async_get_client",
        new_callable=AsyncMock,
        return_value=client,
    ):
        hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

        result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["api_type"] == API_TYPE_DATA_API
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
        data={CONF_API_TYPE: API_TYPE_DATA_API},
        unique_id="data-api",
    )
    config_entry.add_to_hass(hass)

    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = "test-token"

    client = MagicMock()
    client.get_all_devices = AsyncMock(side_effect=exception)

    runtime = TibberDataAPIRuntimeData(session=session)
    with patch.object(
        TibberDataAPIRuntimeData,
        "async_get_client",
        new_callable=AsyncMock,
        return_value=client,
    ):
        hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

        result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["api_type"] == API_TYPE_DATA_API
    assert result["error"] == expected_error
    assert result["devices"] == []
