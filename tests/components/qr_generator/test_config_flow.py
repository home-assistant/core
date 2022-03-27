"""Test the QR Generator config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.qr_generator.config_flow import ConfigFlow
from homeassistant.components.qr_generator.const import (
    CONF_ADVANCED,
    CONF_BACKGROUND_COLOR,
    CONF_BORDER,
    CONF_COLOR,
    CONF_ERROR_CORRECTION,
    CONF_SCALE,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_BORDER,
    DEFAULT_COLOR,
    DEFAULT_ERROR_CORRECTION,
    DEFAULT_SCALE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DUMMY_DATA_SIMPLE: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "Sample content",
    CONF_ADVANCED: False,
}
DUMMY_DATA_SIMPLE_ADVANCED: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "Sample content",
    CONF_ADVANCED: True,
}

DUMMY_DATA_SIMPLE_INVALID_TEMPLATE: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "{{novalid template}}",
    CONF_ADVANCED: False,
}

DUMMY_DATA_ADVANCED: dict[str, Any] = {
    CONF_COLOR: DEFAULT_COLOR,
    CONF_SCALE: DEFAULT_SCALE,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}

DUMMY_DATA_ADVANCED_INVALID_COLOR: dict[str, Any] = {
    CONF_COLOR: "black",
    CONF_SCALE: DEFAULT_SCALE,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}

DUMMY_ENTRY: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "Sample content",
    CONF_ADVANCED: True,
    CONF_COLOR: DEFAULT_COLOR,
    CONF_SCALE: DEFAULT_SCALE,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}

DUMMY_ENTRY_CHANGE: dict[str, Any] = {
    CONF_VALUE_TEMPLATE: "New test",
    CONF_ADVANCED: False,
}

DUMMY_ENTRY_ADVANCED_CHANGE: dict[str, Any] = {
    CONF_SCALE: 50,
}

DUMMY_ENTRY_UPDATED: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "New test",
    CONF_ADVANCED: False,
    CONF_COLOR: DEFAULT_COLOR,
    CONF_SCALE: DEFAULT_SCALE,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}

DUMMY_ENTRY_ADVANCED_UPDATED: dict[str, Any] = {
    CONF_NAME: "Test QR Code",
    CONF_VALUE_TEMPLATE: "Sample content",
    CONF_ADVANCED: True,
    CONF_COLOR: DEFAULT_COLOR,
    CONF_SCALE: 50,
    CONF_BORDER: DEFAULT_BORDER,
    CONF_ERROR_CORRECTION: DEFAULT_ERROR_CORRECTION,
    CONF_BACKGROUND_COLOR: DEFAULT_BACKGROUND_COLOR,
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA_SIMPLE
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DUMMY_DATA_SIMPLE[CONF_NAME]


async def test_step_user_template_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user with an invalid template."""

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA_SIMPLE_INVALID_TEMPLATE
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_template"}


async def test_show_set_form_advanced_from_user(hass: HomeAssistant) -> None:
    """Test that the advanced form is served as a step."""

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=DUMMY_DATA_SIMPLE_ADVANCED
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "advanced"


async def test_show_set_form_advanced(hass: HomeAssistant) -> None:
    """Test that the advanced form is served."""

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "advanced"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "advanced"


async def test_step_advanced(hass: HomeAssistant) -> None:
    """Test starting a flow by advanced with valid values."""

    with patch.object(ConfigFlow, "override_config", DUMMY_DATA_SIMPLE):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "advanced"}, data=DUMMY_DATA_ADVANCED
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DUMMY_DATA_SIMPLE[CONF_NAME]


async def test_step_advanced_invalid_color(hass: HomeAssistant) -> None:
    """Test starting a flow by advanced with an invalid color."""

    with patch.object(ConfigFlow, "override_config", DUMMY_DATA_SIMPLE):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "advanced"},
            data=DUMMY_DATA_ADVANCED_INVALID_COLOR,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "advanced"
        assert result["errors"] == {"base": "invalid_color"}


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DUMMY_ENTRY[CONF_NAME],
        data=DUMMY_ENTRY,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qr_generator.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_ENTRY_CHANGE,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert dict(config_entry.options) == DUMMY_ENTRY_UPDATED


async def test_options_flow_invalid_template(hass: HomeAssistant) -> None:
    """Test config flow options with invalid template."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DUMMY_ENTRY[CONF_NAME],
        data=DUMMY_ENTRY,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qr_generator.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_DATA_SIMPLE_INVALID_TEMPLATE,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {"base": "invalid_template"}


async def test_options_flow_to_advanced(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DUMMY_ENTRY[CONF_NAME],
        data=DUMMY_ENTRY,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qr_generator.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_DATA_SIMPLE_ADVANCED,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "advanced"
        assert result["errors"] == {}


async def test_options_flow_advanced(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DUMMY_ENTRY[CONF_NAME],
        data=DUMMY_ENTRY,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qr_generator.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_DATA_SIMPLE_ADVANCED,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "advanced"
        assert result["errors"] == {}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_ENTRY_ADVANCED_CHANGE,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert dict(config_entry.options) == DUMMY_ENTRY_ADVANCED_UPDATED


async def test_options_flow_advanced_invalid_color(hass: HomeAssistant) -> None:
    """Test config flow options with invalid template."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DUMMY_ENTRY[CONF_NAME],
        data=DUMMY_ENTRY,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qr_generator.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_DATA_SIMPLE_ADVANCED,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "advanced"
        assert result["errors"] == {}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=DUMMY_DATA_ADVANCED_INVALID_COLOR,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "advanced"
        assert result["errors"] == {"base": "invalid_color"}
