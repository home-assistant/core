"""Test Homey Energy Dongle diagnostics."""

import json

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import (
    EON_HU_IDENTIFIER,
    EON_HU_SERIAL_NUMBER,
    EQUIPMENT_IDENTIFIER,
    GAS_METER_IDENTIFIER,
    TELEGRAM_EON_HU,
    TELEGRAM_Q3D,
    TELEGRAM_V5,
)


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redact the meter identifiers."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id"))


@pytest.mark.parametrize(
    ("dsmr_version", "telegram_data", "identifiers"),
    [
        pytest.param("5B", TELEGRAM_V5, [EQUIPMENT_IDENTIFIER], id="belgium"),
        pytest.param(
            "4", TELEGRAM_V5, [EQUIPMENT_IDENTIFIER, GAS_METER_IDENTIFIER], id="dsmr4"
        ),
        pytest.param(
            "Q3D", TELEGRAM_Q3D, ["0272031312565", "1ESY1313002565"], id="q3d"
        ),
        pytest.param(
            "5EONHU",
            TELEGRAM_EON_HU,
            [EON_HU_IDENTIFIER, EON_HU_SERIAL_NUMBER],
            id="hungary",
        ),
    ],
)
async def test_diagnostics_redact_profile_identifiers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    identifiers: list[str],
) -> None:
    """Test identifiers that other DSMR profiles name differently are redacted."""
    diagnostics = json.dumps(
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    )

    for identifier in identifiers:
        assert identifier not in diagnostics
