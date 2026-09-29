"""Tests for Besen diagnostics."""

from unittest.mock import Mock

from besen.models import BesenData, BoardRevision, ChargerInfo, CommandResult
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.besen.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant

from . import publish_besen_state
from .conftest import (
    FIXTURE_ADDRESS,
    FIXTURE_NAME,
    FIXTURE_PIN,
    charger_state,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test the download, redaction, and absence of device commands or mutations."""

    state = charger_state()
    state = state.updated(
        info=state.info.updated(
            advertised_name=FIXTURE_NAME,
            board_revision=BoardRevision.NEW,
        ),
        last_command=CommandResult("set_pin", {"pin": FIXTURE_PIN}),
        last_error=f"Private error for {FIXTURE_ADDRESS}, PIN {FIXTURE_PIN}",
    )
    mock_besen_client.state = state
    await setup_integration(hass, mock_config_entry)
    client_calls = list(mock_besen_client.mock_calls)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot
    assert mock_besen_client.mock_calls == client_calls
    assert mock_besen_client.state is state
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
    result["data"]["info"]["model"] = "Changed in download"
    assert state.info.model == "BS20"


@pytest.mark.parametrize(
    ("available", "authenticated", "auth_failed"),
    [
        pytest.param(False, False, False, id="disconnected"),
        pytest.param(False, False, True, id="authentication-failed"),
        pytest.param(True, False, False, id="connected-not-authenticated"),
    ],
)
async def test_diagnostics_connection_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    available: bool,
    authenticated: bool,
    auth_failed: bool,
) -> None:
    """Test diagnostics reflect the latest pushed connection and login state."""

    await setup_integration(hass, mock_config_entry)
    state = charger_state(available=available, authenticated=authenticated).updated(
        auth_failed=auth_failed
    )
    publish_besen_state(mock_besen_client, state)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert {
        key: result["data"][key]
        for key in ("available", "authenticated", "auth_failed")
    } == snapshot


async def test_diagnostics_missing_readings(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test the download before the charger has reported any readings."""

    mock_besen_client.state = BesenData(info=ChargerInfo(address=FIXTURE_ADDRESS))
    await setup_integration(hass, mock_config_entry, [])

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot


async def test_diagnostics_without_runtime_data(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test redacted configuration is available even if setup never completed."""

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result == snapshot
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
