"""Test the GoodWe number platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.goodwe import CONF_MODEL_FAMILY, DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT, TEST_SERIAL

from tests.common import MockConfigEntry


async def _setup_entry(hass: HomeAssistant) -> None:
    """Set up a GoodWe config entry."""
    config_entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MODEL_FAMILY: "DT",
        },
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_setting_without_value_is_skipped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_inverter: MagicMock,
) -> None:
    """Test a setting read as None is skipped without dropping the other numbers."""
    mock_inverter.settings.return_value = []
    mock_inverter.get_grid_export_limit = AsyncMock(return_value=None)
    mock_inverter.get_ongrid_battery_dod = AsyncMock(return_value=80)

    await _setup_entry(hass)

    assert (
        entity_registry.async_get_entity_id(
            Platform.NUMBER, DOMAIN, f"{DOMAIN}-grid_export_limit-{TEST_SERIAL}"
        )
        is None
    )
    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{DOMAIN}-battery_discharge_depth-{TEST_SERIAL}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "80.0"


async def test_update_without_value_keeps_last_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_inverter: MagicMock,
) -> None:
    """Test an update reading None keeps the last known value."""
    mock_inverter.settings.return_value = []
    mock_inverter.get_grid_export_limit = AsyncMock(return_value=5000)
    mock_inverter.get_ongrid_battery_dod = AsyncMock(return_value=80)

    await _setup_entry(hass)
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{DOMAIN}-grid_export_limit-{TEST_SERIAL}"
    )
    assert entity_id is not None

    mock_inverter.get_grid_export_limit.return_value = None
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5000.0"
