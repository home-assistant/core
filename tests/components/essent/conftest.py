"""Fixtures for Essent integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.essent.const import API_ENDPOINT, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set Home Assistant time zone."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


@pytest.fixture(autouse=True)
def fixed_minute_offset() -> Generator[None, None, None]:
    """Use a predictable API fetch minute offset."""
    with patch(
        "homeassistant.components.essent.coordinator.random.randint", return_value=5
    ):
        yield


@pytest.fixture(autouse=True)
def disable_coordinator_schedules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable scheduler callbacks during tests."""
    monkeypatch.setattr(
        "homeassistant.components.essent.coordinator.EssentDataUpdateCoordinator.start_schedules",
        lambda self: None,
    )


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


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: ClientSessionGenerator,
    response: dict[str, Any],
) -> MockConfigEntry:
    """Set up the Essent integration for testing."""
    aioclient_mock.get(API_ENDPOINT, json=response)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Essent",
        data={},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
