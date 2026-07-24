"""Test the GoodWe diagnostics."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.goodwe import CONF_MODEL_FAMILY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_inverter: MagicMock,
) -> None:
    """Test config entry diagnostics."""

    config_entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MODEL_FAMILY: "ET",
        },
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot(exclude=props("created_at", "modified_at"))
