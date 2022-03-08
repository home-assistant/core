"""Test the switch light config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.integration.const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
    TRAPEZOIDAL_METHOD,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_METHOD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_USER_INPUT = {
    CONF_SOURCE_SENSOR: "sensor.power",
    CONF_ROUND_DIGITS: 3,
    CONF_UNIT_PREFIX: "k",
    CONF_UNIT_TIME: "h",
    CONF_METHOD: TRAPEZOIDAL_METHOD,
}


@pytest.fixture(name="mock_setup_entry", autouse=True)
async def mock_setup_entry_fixture():
    """Fixture to avoid setting up the entry during tests."""
    with patch("homeassistant.components.integration.async_setup_entry") as mock:
        yield mock


async def test_config_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "power integral"
    assert result["data"] == {}
    assert result["options"] == MOCK_USER_INPUT

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_name(hass: HomeAssistant) -> None:
    """Test the config flow name is copied from registry entry, with fallback to state."""
    registry = er.async_get(hass)

    async def _configured_title() -> str:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
        return result["title"]

    # No entry or state, use Object ID
    assert await _configured_title() == "power integral"

    # State set, use name from state
    hass.states.async_set("sensor.power", "0", {ATTR_FRIENDLY_NAME: "State Name"})
    assert await _configured_title() == "State Name integral"

    # Entity registered, use original name from registry entry
    hass.states.async_remove("sensor.power")
    entry = registry.async_get_or_create(
        "sensor",
        "test",
        "unique",
        suggested_object_id="power",
        original_name="Original Name",
    )
    assert entry.entity_id == "sensor.power"
    hass.states.async_set("sensor.power", "on", {ATTR_FRIENDLY_NAME: "State Name"})
    assert await _configured_title() == "Original Name integral"

    # Entity has customized name
    registry.async_update_entity("sensor.power", name="Custom Name")
    assert await _configured_title() == "Custom Name integral"


async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    # No options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)
