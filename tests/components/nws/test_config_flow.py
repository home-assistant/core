"""Test the National Weather Service (NWS) config flow."""

from unittest.mock import AsyncMock

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.nws.const import (
    CONF_LOCATION_ENTITY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


async def _select_menu_option(
    hass: HomeAssistant, flow_id: str, option: str
) -> ConfigFlowResult:
    """Select a menu option and return the resulting form."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": option}
    )


async def test_menu_shown(hass: HomeAssistant, mock_simple_nws_config) -> None:
    """Test that the initial step shows a menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["location", "entity"]


async def test_form_location(
    hass: HomeAssistant, mock_simple_nws_config, mock_setup_entry: AsyncMock
) -> None:
    """Test the specific location configuration path."""
    hass.config.latitude = 35
    hass.config.longitude = -90

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await _select_menu_option(hass, result["flow_id"], "location")
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "location"
    assert result2["errors"] == {}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test"}
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "ABC"
    assert result3["data"] == {
        CONF_API_KEY: "test",
        "latitude": 35,
        "longitude": -90,
        CONF_STATION: "ABC",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_location_cannot_connect(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test we handle cannot connect error in location path."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "location")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_location_unknown_error(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test we handle unknown error in location path."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "location")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_location_already_configured(
    hass: HomeAssistant, mock_simple_nws_config, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle duplicate location entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "location")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1

    mock_setup_entry.reset_mock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "location")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_entity(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the entity-based configuration path."""
    entry = entity_registry.async_get_or_create("person", "person", "test_user")
    entity_registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "person.person_test_user"
    assert result2["data"] == {
        CONF_API_KEY: "test",
        CONF_LOCATION_ENTITY: entry.id,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_entity_no_coordinates(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity path with entity that has no coordinates."""
    entry = entity_registry.async_get_or_create("person", "person", "no_gps")
    entity_registry.async_get_or_create("person", "person", "also_no_gps")
    hass.states.async_set(entry.entity_id, "unknown", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_no_coordinates"}


async def test_form_entity_non_numeric_coordinates(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity path with entity that has non-numeric coordinates."""
    entry = entity_registry.async_get_or_create("person", "person", "bad_gps")
    entity_registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: "not_a_number", ATTR_LONGITUDE: "also_not"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_no_coordinates"}


async def test_form_entity_not_found(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test entity path with entity not in registry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: "person.nonexistent"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_not_found"}


async def test_form_entity_disabled(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity path with disabled entity."""
    entry = entity_registry.async_get_or_create("person", "person", "disabled_user")
    entity_registry.async_get_or_create("person", "person", "other_user")
    entity_registry.async_update_entity(
        entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_disabled"}


async def test_form_entity_cannot_connect(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we handle cannot connect error in entity path."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = aiohttp.ClientError

    entry = entity_registry.async_get_or_create("person", "person", "test_user")
    entity_registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_entity_already_configured(
    hass: HomeAssistant,
    mock_simple_nws_config,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we handle duplicate entity-based entries."""
    entry = entity_registry.async_get_or_create("person", "person", "test_user")
    entity_registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _select_menu_option(hass, result["flow_id"], "entity")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test", CONF_LOCATION_ENTITY: entry.entity_id},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
