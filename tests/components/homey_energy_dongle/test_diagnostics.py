"""Test Homey Energy Dongle diagnostics."""

import json

from homey_energy_dongle_ws import parse_telegram
from homey_energy_dongle_ws.parser import TELEGRAM_SPECIFICATIONS
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import EQUIPMENT_IDENTIFIER, TELEGRAM_Q3D, TELEGRAM_V5

GAS_METER_IDENTIFIER = "3232323241424344313233343536373839"


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
    ("telegram", "identifiers"),
    [
        pytest.param(
            parse_telegram(
                TELEGRAM_V5, telegram_specification=TELEGRAM_SPECIFICATIONS["5B"]
            ),
            [EQUIPMENT_IDENTIFIER],
            id="belgium",
        ),
        pytest.param(
            parse_telegram(
                TELEGRAM_V5, telegram_specification=TELEGRAM_SPECIFICATIONS["4"]
            ),
            [EQUIPMENT_IDENTIFIER, GAS_METER_IDENTIFIER],
            id="dsmr4",
        ),
        pytest.param(
            parse_telegram(
                TELEGRAM_Q3D, telegram_specification=TELEGRAM_SPECIFICATIONS["Q3D"]
            ),
            ["0272031312565", "1ESY1313002565"],
            id="q3d",
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
