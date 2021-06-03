"""Test the FX Luminaire Luxor low voltage controller config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.luxor import const
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.luxor.config_flow.validate_luxor",
        return_value=True,
    ), patch(
        "homeassistant.components.luxor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Luxor Controller"
    assert result2["data"] == {
        "host": "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.luxor.config_flow.validate_luxor",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass):
    """Test options config flow."""
    entry = MockConfigEntry(
        domain="luxor",
        data={"host": "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert (
        _get_schema_default(schema, const.CONF_INCLUDE_LUXOR_THEMES)
        == const.DEFAULT_INCLUDE_LUXOR_THEMES
    )
    assert (
        _get_schema_default(schema, const.CONF_INCLUDE_LUXOR_THEMES)
        == const.DEFAULT_INCLUDE_LUXOR_THEMES
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.CONF_INCLUDE_LUXOR_THEMES: True,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        const.CONF_INCLUDE_LUXOR_THEMES: True,
    }


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")
