"""Tests for the Aquarite diagnostics."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aquarite.const import CONF_POOL_ID, DOMAIN
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
        title=MOCK_POOL_NAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_POOL_ID: MOCK_POOL_ID,
        },
        unique_id=MOCK_POOL_ID,
    )


async def test_diagnostics_redacts_credentials_and_location(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test diagnostics redacts username, password, and location PII."""
    mock_entry.add_to_hass(hass)

    coord = MagicMock()
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.subscribe = AsyncMock()
    coord.setup_tasks = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.data = mock_pool_data
    coord.pool_id = MOCK_POOL_ID

    with (
        patch("homeassistant.components.aquarite.AquariteAuth") as mock_auth_cls,
        patch("homeassistant.components.aquarite.AquariteClient"),
        patch(
            "homeassistant.components.aquarite.AquariteDataUpdateCoordinator",
            return_value=coord,
        ),
    ):
        mock_auth_cls.return_value = AsyncMock()
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    # Entry data is redacted
    assert diagnostics["entry"]["title"] == MOCK_POOL_NAME
    assert diagnostics["entry"]["data"][CONF_USERNAME] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

    # Location PII in coordinator data is redacted
    form = diagnostics["coordinator_data"]["form"]
    assert form["city"] == "**REDACTED**"
    assert form["street"] == "**REDACTED**"
    assert form["zipcode"] == "**REDACTED**"
    assert form["lat"] == "**REDACTED**"
    assert form["lng"] == "**REDACTED**"
    # Country is NOT in the redact list
    assert form["country"] == "BE"
