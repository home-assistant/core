"""Test the GoodWe number platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.goodwe import CONF_MODEL_FAMILY, DOMAIN
from homeassistant.components.number import ATTR_MAX
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_HOST, TEST_PORT, TEST_SERIAL

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("rated_power", "expected_max"),
    [
        pytest.param(29900, 29900, id="above_default_max"),
        pytest.param(5000, 10000, id="below_default_max"),
    ],
)
async def test_grid_export_limit_max(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_inverter: MagicMock,
    rated_power: int,
    expected_max: int,
) -> None:
    """Test the export limit in watts goes up to the rated power of the inverter."""
    mock_inverter.rated_power = rated_power
    mock_inverter.settings.return_value = []
    mock_inverter.get_grid_export_limit = AsyncMock(return_value=14400)
    mock_inverter.get_ongrid_battery_dod = AsyncMock(return_value=50)
    config_entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT, CONF_MODEL_FAMILY: "ET"},
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.goodwe.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{DOMAIN}-grid_export_limit-{TEST_SERIAL}"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_MAX] == expected_max
