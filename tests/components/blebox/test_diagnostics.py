"""Tests for BleBox diagnostics."""

import blebox_uniapi.switch
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import mock_feature

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="switchbox", autouse=True)
def switchbox_fixture() -> None:
    """Set up a switch product mock."""
    mock_feature("switches", blebox_uniapi.switch.Switch)


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param(
            {CONF_HOST: "172.100.123.4", CONF_PORT: 80},
            id="no_credentials",
        ),
        pytest.param(
            {
                CONF_HOST: "172.100.123.4",
                CONF_PORT: 80,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "secret",
            },
            id="with_credentials",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    entry_data: dict,
) -> None:
    """Test diagnostics output, including credential redaction."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot(
        exclude=props("entry_id", "created_at", "modified_at")
    )
