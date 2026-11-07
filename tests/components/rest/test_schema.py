"""Tests for RESTful schema.py."""

from typing import Any

from probatio import Invalid
import pytest

from homeassistant.components.rest.schema import (
    RESOURCE_FLOW_SCHEMA,
    KeyedTemplateSelector,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant


def test_keyed_template_selector_duplicate_keys(
    hass: HomeAssistant,
) -> None:
    """Test if the KeyedTemplateSelector validation raises for duplicate keys."""

    kts = KeyedTemplateSelector("test_selector")

    with pytest.raises(Invalid) as ex:
        kts(
            [
                {"key": "test_key", "value": "test_value"},
                {"key": "test_key", "value": "test_value1"},
            ]
        )

    assert "Duplicate keys" in str(ex)


def test_resource_schema_invalid_authentication(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test config entry flow schema validation."""
    user_input = get_config_entry_data
    user_input[CONF_AUTHENTICATION][CONF_USERNAME] = "test_user"
    with pytest.raises(Invalid) as ex:
        RESOURCE_FLOW_SCHEMA()(user_input)

    assert ex.value.error_message == "credentials_missing"

    with pytest.raises(Invalid) as ex:
        RESOURCE_FLOW_SCHEMA()(
            get_config_entry_data
            | {  # missing auth method
                CONF_AUTHENTICATION: {"extra_key": "fake_data"}
            }
        )

    assert ex.value.error_message == "not a valid option"


def test_resource_template_error(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test template validation error handling."""

    with pytest.raises(Invalid) as ex:
        RESOURCE_FLOW_SCHEMA()(
            get_config_entry_data
            | {CONF_RESOURCE: "http://fakeurl.com/{{ param[5] }}"},
        )

    assert "UndefinedError" in ex.value.error_message


async def test_keyed_template_selector_error(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test template render error handling."""

    with pytest.raises(Invalid) as ex:
        RESOURCE_FLOW_SCHEMA()(
            get_config_entry_data
            | {CONF_HEADERS: [{"key": "Fake-Header", "value": "{{ 1/0 }}"}]},
        )

    assert (ex.value.path) == [CONF_HEADERS]
    assert "ZeroDivisionError" in str(ex.value.error_message)


def test_resource_schema_payload_template_error(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test a template render error."""

    with pytest.raises(Invalid) as ex:
        RESOURCE_FLOW_SCHEMA()(get_config_entry_data | {CONF_PAYLOAD: "{{ 1 / 0}}"})
    assert "ZeroDivisionError" in ex.value.error_message
    assert ex.value.path == [CONF_PAYLOAD]
