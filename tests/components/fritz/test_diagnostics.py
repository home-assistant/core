"""Tests for Fritz!Tools diagnostics platform."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_FB_SERVICES, MOCK_USER_DATA


@pytest.mark.parametrize(
    "removed_services",
    [
        pytest.param([], id="default"),
        pytest.param(["LANConfigSecurity1"], id="no_lan_config_security"),
    ],
)
@pytest.mark.usefixtures("fh_class_mock", "fs_class_mock")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock: MagicMock,
    snapshot: SnapshotAssertion,
    removed_services: list[str],
) -> None:
    """Test config entry diagnostics."""
    fc_data = deepcopy(MOCK_FB_SERVICES)
    for service in removed_services:
        fc_data.pop(service)
    fc_class_mock.return_value.override_services(fc_data)

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "last_activity")
    )
