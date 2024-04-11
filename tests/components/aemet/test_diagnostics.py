"""Define tests for the AEMET OpenData diagnostics."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.aemet.const import DOMAIN
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-02-23T18:00:00+00:00")
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)

    assert hass.data[DOMAIN]
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(
        "homeassistant.components.aemet.AEMET.raw_data",
        return_value={},
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        assert result == snapshot
