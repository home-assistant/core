"""Fixtures for Essent integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from essent_dynamic_pricing import EssentClient, EssentPrices
from homeassistant.components.essent.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set Home Assistant time zone."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


@pytest.fixture
def essent_api_response() -> dict[str, Any]:
    """Combined response helper for full integration tests."""
    return load_json_object_fixture("essent_api_response.json", "essent")


@pytest.fixture
def electricity_api_response() -> dict[str, Any]:
    """Load sample electricity API response."""
    return load_json_object_fixture("electricity_api_response.json", "essent")


@pytest.fixture
def gas_api_response() -> dict[str, Any]:
    """Load sample gas API response."""
    return load_json_object_fixture("gas_api_response.json", "essent")


@pytest.fixture
def partial_gas_api_response() -> dict[str, Any]:
    """Load sample response missing gas for tomorrow."""
    return load_json_object_fixture("partial_gas_api_response.json", "essent")


class _MockResponse:
    """Simple mock response for client normalization in tests."""

    def __init__(self, body: dict[str, Any]) -> None:
        self.status = 200
        self._body = body

    async def text(self) -> str:
        """Return body as text."""
        return repr(self._body)

    async def json(self) -> dict[str, Any]:
        """Return JSON body."""
        return self._body


class _MockSession:
    """Mock session returning the given response."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._response = _MockResponse(body)

    async def get(self, *args: Any, **kwargs: Any) -> _MockResponse:
        """Return the mock response."""
        return self._response


@pytest.fixture
async def essent_normalized_data(
    essent_api_response: dict[str, Any],
) -> EssentPrices:
    """Normalize the sample API payload using the library client."""
    client = EssentClient(_MockSession(essent_api_response))
    return await client.async_get_prices()


@pytest.fixture
async def partial_gas_normalized_data(
    partial_gas_api_response: dict[str, Any],
) -> EssentPrices:
    """Normalize the gas sample that lacks tariffs for tomorrow."""
    client = EssentClient(_MockSession(partial_gas_api_response))
    return await client.async_get_prices()


@pytest.fixture(autouse=True)
def patch_essent_client(essent_normalized_data: EssentPrices) -> Generator:
    """Patch EssentClient to avoid real HTTP during tests."""
    mock_client = AsyncMock()
    mock_client.async_get_prices.return_value = essent_normalized_data
    with patch(
        "homeassistant.components.essent.coordinator.EssentClient",
        return_value=mock_client,
    ):
        yield mock_client


async def setup_integration(
    hass: HomeAssistant,
    *,
    pref_disable_polling: bool = False,
) -> MockConfigEntry:
    """Set up the Essent integration for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Essent",
        data={},
        unique_id=DOMAIN,
        pref_disable_polling=pref_disable_polling,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
