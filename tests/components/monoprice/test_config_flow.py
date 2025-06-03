"""Test the Monoprice 6-Zone Amplifier config flow."""

from unittest.mock import patch

from serial import SerialException

from homeassistant import config_entries
from homeassistant.components.monoprice.const import (
    CONF_SOURCE_1,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCES,
    DOMAIN,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {
    CONF_PORT: "/test/port",
    CONF_SOURCE_1: "one",
    CONF_SOURCE_4: "four",
    CONF_SOURCE_5: "    ",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.monoprice.config_flow.get_monoprice",
            return_value=True,
        ),
        patch(
            "homeassistant.components.monoprice.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[CONF_PORT]
    assert result2["data"] == {
        CONF_PORT: CONFIG[CONF_PORT],
        CONF_SOURCES: {"1": CONFIG[CONF_SOURCE_1], "4": CONFIG[CONF_SOURCE_4]},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.monoprice.config_flow.get_monoprice",
        side_effect=SerialException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_generic_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot generic exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.monoprice.config_flow.get_monoprice",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    conf = {CONF_PORT: "/test/port", CONF_SOURCES: {"4": "four"}}

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=conf,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.monoprice.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SOURCE_1: "one", CONF_SOURCE_4: "", CONF_SOURCE_5: "five"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_SOURCES] == {"1": "one", "5": "five"}
