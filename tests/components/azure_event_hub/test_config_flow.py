"""Test the Azure Event Hub config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.azure_event_hub.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidConfig,
    InvalidConnectionString,
    InvalidDomain,
    InvalidEntity,
    InvalidFilter,
    InvalidInstance,
    InvalidNamespace,
    InvalidSAS,
)
from homeassistant.components.azure_event_hub.const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_FILTER,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    DOMAIN,
)

from tests.common import mock_coro

CONFIG_IN = {
    CONF_EVENT_HUB_CON_STRING: "Endpoint=sb://testehns.servicebus.windows.net/;SharedAccessKeyName=testpolicy;SharedAccessKey=testkey;EntityPath=test",
    CONF_FILTER: False,
}
CONFIG_OUT = {
    CONF_EVENT_HUB_CON_STRING: "Endpoint=sb://testehns.servicebus.windows.net/;SharedAccessKeyName=testpolicy;SharedAccessKey=testkey;EntityPath=test",
    CONF_FILTER: {
        CONF_EXCLUDE_DOMAINS: [],
        CONF_EXCLUDE_ENTITIES: [],
        CONF_INCLUDE_DOMAINS: [],
        CONF_INCLUDE_ENTITIES: [],
    },
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        return_value=mock_coro([CONFIG_OUT, "testname"]),
    ), patch(
        "homeassistant.components.azure_event_hub.async_setup",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.azure_event_hub.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "testname"
    assert result2["data"] == CONFIG_OUT
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = CannotConnect
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidAuth
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_config(hass):
    """Test we handle invalid config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidConfig
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_connection_string(hass):
    """Test we handle invalid connection string."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidConnectionString
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_domain(hass):
    """Test we handle invalid domain in filters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidDomain
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_entity(hass):
    """Test we handle invalid entity names."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidEntity
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_filter(hass):
    """Test we handle invalid filters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidFilter
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_instance(hass):
    """Test we handle invalid instance names."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidInstance
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_namespace(hass):
    """Test we handle invalid namespace."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidNamespace
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}


async def test_form_invalid_sas(hass):
    """Test we handle invalid sas policy and key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    test_error = InvalidSAS
    with patch(
        "homeassistant.components.azure_event_hub.config_flow.validate_input",
        side_effect=test_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_IN
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": test_error.msg}
