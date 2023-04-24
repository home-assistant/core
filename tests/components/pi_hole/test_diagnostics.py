"""Test pi_hole component."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components import pi_hole
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA_DEFAULTS, _create_mocked_hole, _patch_init_hole

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests diagnostics."""
    mocked_hole = _create_mocked_hole()
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN, data=CONFIG_DATA_DEFAULTS, entry_id="pi_hole_mock_entry"
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
