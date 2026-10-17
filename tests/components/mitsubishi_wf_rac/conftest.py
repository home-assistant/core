"""Fixtures for the Mitsubishi WF-RAC integration."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from pywfrac import (
    Aircon,
    AirconCommands,
    AirconStat,
    AirconStatus,
    FirmwareInfo,
    RacParser,
    Repository,
)

from homeassistant.components.mitsubishi_wf_rac.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import AIRCO_ID, ENTRY_DATA

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mitsubishi_wf_rac.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def aircon_stat() -> dict[str, Any]:
    """Return one getAirconStat answer, as the module sends it."""
    return load_json_object_fixture("aircon_stat.json", DOMAIN)


@pytest.fixture
def aircon_fields() -> dict[str, Any]:
    """Fields to change on the captured state; override with parametrize."""
    return {}


@pytest.fixture
def aircon(aircon_stat: dict[str, Any], aircon_fields: dict[str, Any]) -> Aircon:
    """Return the state the unit reports: off, cooling, set to 22 degrees."""
    captured = RacParser().translate_bytes(aircon_stat["airconStat"])
    return replace(captured, **aircon_fields)


@pytest.fixture
def no_consolidation_window() -> Generator[None]:
    """Send commands right away, since the frozen clock never ends the window."""
    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator."
        "UPDATE_CONSOLIDATION_PERIOD",
        timedelta(0),
    ):
        yield


@pytest.fixture
def repository_class(
    aircon: Aircon, aircon_stat: dict[str, Any]
) -> Generator[MagicMock]:
    """Patch pywfrac's Repository where the integration builds one.

    The fake unit applies the commands it is sent, so later polls follow them.
    """
    status = AirconStatus(
        aircon=aircon,
        firmware=FirmwareInfo.from_contents(aircon_stat),
        expires=aircon_stat["expires"],
    )

    parser = RacParser()

    async def send_command(
        airco_id: str, base: Aircon, params: dict[AirconCommands, Any]
    ) -> Aircon:
        # A refused write makes the library re-encode from the unit's fresh state.
        if repository.fresh_state is not None:
            base = repository.fresh_state
            repository.fresh_state = None
        stat = AirconStat.from_aircon(base)
        for key, value in params.items():
            setattr(stat, key, value)
        status.aircon = parser.translate_bytes(parser.to_base64(stat))
        return status.aircon

    repository = create_autospec(Repository, instance=True)
    repository.get_airco_id.return_value = AIRCO_ID
    repository.async_unregister.return_value = True
    repository.async_get_status.return_value = status
    repository.async_send_command.side_effect = send_command
    repository.method = "https"
    # Set a state here to make the next command start from it, not from base.
    repository.fresh_state = None

    cls = MagicMock(return_value=repository)
    with (
        patch("homeassistant.components.mitsubishi_wf_rac.Repository", cls),
        patch("homeassistant.components.mitsubishi_wf_rac.config_flow.Repository", cls),
    ):
        yield cls


@pytest.fixture
def mock_repository(repository_class: MagicMock) -> MagicMock:
    """Return the library client every part of the integration shares."""
    return repository_class.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry at the current version."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data=ENTRY_DATA,
        unique_id=AIRCO_ID,
        version=8,
        minor_version=2,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with a reachable airco."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
