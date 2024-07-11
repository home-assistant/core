"""Test the CO2Signal diagnostics."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.goodwe import CONF_MODEL_FAMILY, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_MODEL_FAMILY: "ET"},
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
    )
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.goodwe.connect", return_value=mock_inverter):
        assert await async_setup_component(hass, DOMAIN, {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot
