"""Test Environment Canada diagnostics."""

import json
from typing import Any

from syrupy import SnapshotAssertion

from homeassistant.components.environment_canada.const import CONF_STATION
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

FIXTURE_USER_INPUT = {
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 42.42,
    CONF_STATION: "XX/1234567",
    CONF_LANGUAGE: "Gibberish",
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    ec_data: dict[str, Any],
) -> None:
    """Test config entry diagnostics."""

    ec_data = json.loads(
        load_fixture("environment_canada/current_conditions_data.json")
    )

    config_entry = await init_integration(hass, ec_data)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot
