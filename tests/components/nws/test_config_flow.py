"""Test the National Weather Service (NWS) config flow."""

from unittest.mock import patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.nws.const import (
    CONF_LOCATION_ENTITY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


async def test_form(hass: HomeAssistant, mock_simple_nws_config) -> None:
    """Test we get the form."""
    hass.config.latitude = 35
    hass.config.longitude = -90

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "test"}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ABC"
    assert result2["data"] == {
        "api_key": "test",
        "latitude": 35,
        "longitude": -90,
        "station": "ABC",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant, mock_simple_nws_config) -> None:
    """Test we handle cannot connect error."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant, mock_simple_nws_config) -> None:
    """Test we handle unknown error."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test we handle duplicate entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_with_location_entity(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test config flow with a location entity selected."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("person", "person", "test_user")
    registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test", "location_entity": entry.entity_id},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ABC"
    assert result2["data"][CONF_LOCATION_ENTITY] == entry.id
    assert result2["data"]["latitude"] == 40.0
    assert result2["data"]["longitude"] == -80.0
    assert CONF_STATION not in result2["data"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_location_entity_and_station(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test config flow with a location entity and explicit station."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("zone", "zone", "office")
    registry.async_get_or_create("zone", "zone", "home")
    hass.states.async_set(
        entry.entity_id,
        "zoning",
        {ATTR_LATITUDE: 42.0, ATTR_LONGITUDE: -82.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test",
                "location_entity": entry.entity_id,
                "station": "XYZ",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_LOCATION_ENTITY] == entry.id
    assert result2["data"][CONF_STATION] == "XYZ"
    assert result2["data"]["latitude"] == 42.0
    assert result2["data"]["longitude"] == -82.0
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_location_entity_no_coordinates(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test config flow with entity that has no coordinates."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("person", "person", "no_gps")
    registry.async_get_or_create("person", "person", "also_no_gps")
    hass.states.async_set(entry.entity_id, "unknown", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test", "location_entity": entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_no_coordinates"}


async def test_form_with_location_entity_non_numeric_coordinates(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test config flow with entity that has non-numeric coordinates."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("person", "person", "bad_gps")
    registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: "not_a_number", ATTR_LONGITUDE: "also_not"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test", "location_entity": entry.entity_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_no_coordinates"}


async def test_form_with_location_entity_not_found(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test config flow with entity not in registry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test", "location_entity": "person.nonexistent"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "entity_not_found"}


async def test_form_with_location_entity_already_configured(
    hass: HomeAssistant, mock_simple_nws_config
) -> None:
    """Test we handle duplicate entity-based entries."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("person", "person", "test_user")
    registry.async_get_or_create("person", "person", "other_user")
    hass.states.async_set(
        entry.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test", "location_entity": entry.entity_id},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test", "location_entity": entry.entity_id},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
