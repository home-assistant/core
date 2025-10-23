"""Test huawei_lte diagnostics."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import magic_client

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    huawei_lte = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: "http://huawei-lte.example.com"}
    )
    huawei_lte.add_to_hass(hass)
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch(
            "homeassistant.components.huawei_lte.Client", return_value=magic_client()
        ),
    ):
        await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, huawei_lte)
    assert result == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
