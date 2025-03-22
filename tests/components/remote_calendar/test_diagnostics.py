"""Test the remote calendar diagnostics."""

import datetime
from unittest.mock import AsyncMock
import zoneinfo

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

from httpx import ConnectError, Response, UnsupportedProtocol
import pytest
import respx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CALENDER_URL, TEST_ENTITY

from tests.common import MockConfigEntry


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
    assert result == snapshot(exclude=props("created_at", "modified_at"))
