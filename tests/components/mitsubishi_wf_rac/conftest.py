"""Fixtures for the Mitsubishi WF-RAC integration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mitsubishi_wf_rac.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import AIRCO_ID, ENTRY_DATA, ENTRY_OPTIONS

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mitsubishi_wf_rac.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def aircon_stat() -> dict:
    """Return one getAirconStat response, as the module sends it."""
    return json.loads(load_fixture("aircon_stat.json", DOMAIN))


@pytest.fixture
def mock_repository(aircon_stat: dict) -> Generator[AsyncMock]:
    """Patch pywfrac's Repository everywhere the integration builds one.

    Both modules import the class by name, so patching the library itself
    would leave those references untouched.
    """
    repository = AsyncMock()
    repository.get_airco_id.return_value = AIRCO_ID
    repository.update_account_info.return_value = {"result": 0}
    repository.del_account_info.return_value = {"result": 0}
    repository.get_aircon_stats.return_value = aircon_stat
    repository.send_airco_command.return_value = aircon_stat["airconStat"]
    repository.method = "https"
    repository.result_codes = {}

    with (
        patch(
            "homeassistant.components.mitsubishi_wf_rac.coordinator.Repository",
            return_value=repository,
        ),
        patch(
            "homeassistant.components.mitsubishi_wf_rac.config_flow.Repository",
            return_value=repository,
        ),
    ):
        yield repository


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry at the current version."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        unique_id=AIRCO_ID,
        version=5,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with a reachable airco."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
