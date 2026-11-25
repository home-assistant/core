"""Tests for the InfluxDB diagnostics."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.influxdb.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import BASE_V1_CONFIG, BASE_V2_CONFIG, INFLUX_CLIENT_PATH


@pytest.mark.parametrize(
    ("client_path", "config"),
    [
        pytest.param(
            INFLUX_CLIENT_PATH,
            BASE_V1_CONFIG | {CONF_USERNAME: "user", CONF_PASSWORD: "password"},
            id="v1",
        ),
        pytest.param(f"{INFLUX_CLIENT_PATH}V2", BASE_V2_CONFIG, id="v2"),
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    client_path: str,
    config: dict[str, Any],
) -> None:
    """Test config entry diagnostics redact the credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    with patch(client_path):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
        )

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
