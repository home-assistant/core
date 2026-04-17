"""Tests for the Aquarite diagnostics."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aquarite.const import DOMAIN
from homeassistant.components.aquarite.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id=MOCK_USERNAME.lower(),
    )


async def test_diagnostics_redacts_credentials_and_location(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test diagnostics redacts username, password, and location PII."""
    mock_entry.add_to_hass(hass)

    coord = MagicMock()
    coord.pool_id = MOCK_POOL_ID
    coord.pool_name = MOCK_POOL_NAME
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.subscribe = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.data = mock_pool_data

    api = AsyncMock()
    api.get_pools = AsyncMock(return_value={MOCK_POOL_ID: MOCK_POOL_NAME})

    with (
        patch(
            "homeassistant.components.aquarite.AquariteAuth", return_value=AsyncMock()
        ),
        patch("homeassistant.components.aquarite.AquariteClient", return_value=api),
        patch(
            "homeassistant.components.aquarite.AquariteDataUpdateCoordinator",
            return_value=coord,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    # Entry data is redacted
    assert diagnostics["entry"]["title"] == MOCK_USERNAME
    assert diagnostics["entry"]["data"][CONF_USERNAME] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

    # Pool data contains the mock pool keyed by pool_id
    assert MOCK_POOL_ID in diagnostics["pools"]
    pool = diagnostics["pools"][MOCK_POOL_ID]
    assert pool["name"] == MOCK_POOL_NAME

    # Location PII in coordinator data is redacted
    form = pool["data"]["form"]
    assert form["city"] == "**REDACTED**"
    assert form["street"] == "**REDACTED**"
    assert form["zipcode"] == "**REDACTED**"
    assert form["lat"] == "**REDACTED**"
    assert form["lng"] == "**REDACTED**"
    # Country is NOT in the redact list
    assert form["country"] == "BE"
