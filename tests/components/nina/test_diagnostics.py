"""Test the Nina diagnostics."""

from typing import Any
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import mocked_request_function

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

ENTRY_DATA: dict[str, Any] = {
    "slots": 5,
    "regions": {"083350000000": "Aach, Stadt"},
    "filters": {
        "headline_filter": ".*corona.*",
        "area_filter": ".*",
    },
}


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        config_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
            == snapshot
        )
