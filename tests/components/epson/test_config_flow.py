"""Test the epson config flow."""
from unittest.mock import patch

from epson_projector.const import PWR_OFF_STATE

from homeassistant import config_entries
from homeassistant.components.epson.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch("homeassistant.components.epson.Projector.get_power", return_value="01"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER
    with patch(
        "homeassistant.components.epson.Projector.get_power",
        return_value="01",
    ), patch(
        "homeassistant.components.epson.Projector.get_serial_number",
        return_value="12345",
    ), patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-epson"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epson.Projector.get_power",
        return_value=STATE_UNAVAILABLE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_powered_off(hass: HomeAssistant) -> None:
    """Test we handle powered off during initial configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epson.Projector.get_power",
        return_value=PWR_OFF_STATE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "powered_off"}
