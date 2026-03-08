"""Test the remote calendar diagnostics."""

import datetime

from httpx import Response
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CALENDER_URL

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@respx.mock
@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5))
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    ics_content: str,
) -> None:
    """Test config entry diagnostics."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot
