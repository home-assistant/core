"""Test the epson config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.epson.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_UNAVAILABLE


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.epson.Projector.get_property",
        return_value="04",
    ), patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson", CONF_PORT: 80},
        )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-epson"
    assert result2["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 80}
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epson.Projector.get_property",
        return_value=STATE_UNAVAILABLE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson", CONF_PORT: 80},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass):
    """Test config.yaml import."""
    with patch(
        "homeassistant.components.epson.Projector.get_property",
        return_value="04",
    ), patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson", CONF_PORT: 80},
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "test-epson"
        assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 80}


async def test_import_cannot_connect(hass):
    """Test we handle cannot connect error with import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    with patch(
        "homeassistant.components.epson.Projector.get_property",
        return_value=STATE_UNAVAILABLE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_NAME: "test-epson", CONF_PORT: 80},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
