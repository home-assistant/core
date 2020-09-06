"""Test the epson config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.epson.const import DOMAIN, TIMEOUT_SCALE
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    STATE_UNAVAILABLE,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value="04",
    ), patch(
        "homeassistant.components.epson.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-epson"
    assert result2["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 80, CONF_SSL: False}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value=STATE_UNAVAILABLE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass):
    """Test EpsonOptionsFlowHandler."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "test-epson",
            CONF_PORT: 80,
            CONF_SSL: False,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value="04",
    ), patch("homeassistant.components.epson.async_setup", return_value=True), patch(
        "homeassistant.components.epson.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={TIMEOUT_SCALE: 1.5}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {TIMEOUT_SCALE: 1.5}


async def test_import(hass):
    """Test config.yaml import."""
    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value="04",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "test-epson"
        assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 80, CONF_SSL: False}


async def test_import_cannot_connect(hass):
    """Test we handle cannot connect error with import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value=STATE_UNAVAILABLE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_already_configured(hass):
    """Test config.yaml import."""
    with patch(
        "homeassistant.components.epson.config_flow.epson.Projector.get_property",
        return_value="04",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "test-epson"
        assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 80, CONF_SSL: False}
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test-epson",
                CONF_PORT: 80,
                CONF_SSL: False,
            },
        )
        assert result2["type"] == "abort"
        assert result2["reason"] == "already_configured"
