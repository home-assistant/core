"""Tests for Besen diagnostics."""

import json
from unittest.mock import Mock

from besen.models import BesenData, BoardRevision, ChargerInfo, CommandResult
import pytest

from homeassistant.components.besen.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
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

    assert result["entry_data"] == {
        CONF_ADDRESS: REDACTED,
        CONF_NAME: REDACTED,
        CONF_PIN: REDACTED,
    }
    data = result["data"]
    assert set(data) == {
        "info",
        "config",
        "charge",
        "available",
        "authenticated",
        "auth_failed",
    }
    assert data["info"] == {
        "address": REDACTED,
        "serial": REDACTED,
        "charger_type": None,
        "phases": 1,
        "manufacturer": "Besen",
        "model": "BS20",
        "hardware_version": "HW1",
        "software_version": "SW1",
        "output_power": None,
        "output_max_amps": 32,
        "feature": None,
        "support": None,
        "board_revision": "new",
        "advertised_name": REDACTED,
    }
    assert data["config"] == {
        "charge_amps": 16,
        "lcd_brightness": None,
        "system_time": None,
        "system_time_raw": None,
        "temperature_unit": "Celsius",
        "language": None,
        "device_name": REDACTED,
        "rssi": -55,
    }
    assert data["charge"]["power"] == 3500
    assert data["charge"]["total_energy"] == 12.3
    assert data["charge"]["session_energy"] == 1.2
    assert data["charge"]["error_details"] == "No Error"
    assert data["available"] is True
    assert data["authenticated"] is True
    assert data["auth_failed"] is False

    serialized = json.dumps(result)
    for private_value in (
        FIXTURE_ADDRESS,
        FIXTURE_NAME,
        FIXTURE_PIN,
        "SERIAL",
        "Garage",
        "Private error",
    ):
        assert private_value not in serialized
    assert "last_command" not in data
    assert "last_error" not in data

    assert mock_besen_client.mock_calls == client_calls
    assert mock_besen_client.state is state
    assert state.info.serial == "SERIAL"
    assert state.info.advertised_name == FIXTURE_NAME
    assert state.config.device_name == "Garage"
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
    data["info"]["model"] = "Changed in download"
    assert state.info.model == "BS20"


@pytest.mark.parametrize(
    ("available", "authenticated", "auth_failed"),
    [(False, False, False), (False, False, True), (True, False, False)],
)
async def test_diagnostics_connection_state(
    hass: HomeAssistant,
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

    assert result["data"]["available"] is available
    assert result["data"]["authenticated"] is authenticated
    assert result["data"]["auth_failed"] is auth_failed
    assert result["data"]["charge"]["power"] == 3500
    assert result["data"]["info"]["address"] == REDACTED


async def test_diagnostics_missing_readings(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test the download before the charger has reported any readings."""

    mock_besen_client.state = BesenData(info=ChargerInfo(address=FIXTURE_ADDRESS))
    await setup_integration(hass, mock_config_entry, [])

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["data"]["info"]["address"] == REDACTED
    assert result["data"]["info"]["model"] is None
    assert result["data"]["charge"]["power"] is None
    assert result["data"]["config"]["charge_amps"] is None
    assert result["data"]["available"] is False
    assert result["data"]["authenticated"] is False


async def test_diagnostics_without_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test redacted configuration is available even if setup never completed."""

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result == {
        "entry_data": {
            CONF_ADDRESS: REDACTED,
            CONF_NAME: REDACTED,
            CONF_PIN: REDACTED,
        }
    }
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
