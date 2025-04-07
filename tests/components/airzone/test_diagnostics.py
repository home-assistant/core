"""The diagnostics tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.const import RAW_HVAC, RAW_VERSION, RAW_WEBSERVER
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.core import HomeAssistant

from .util import (
    HVAC_MOCK,
    HVAC_VERSION_MOCK,
    HVAC_WEBSERVER_MOCK,
    async_init_integration,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.raw_data",
        return_value={
            RAW_HVAC: HVAC_MOCK,
            RAW_VERSION: HVAC_VERSION_MOCK,
            RAW_WEBSERVER: HVAC_WEBSERVER_MOCK,
        },
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        assert result == snapshot(exclude=props("created_at", "modified_at"))
