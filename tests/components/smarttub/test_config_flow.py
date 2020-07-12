"""Test the smarttub config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.smarttub.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.smarttub.config_flow.validate_credentials",
        autospec=True,
        return_value=True,
    ), patch(
        "homeassistant.components.smarttub.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.smarttub.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "test-email", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email"
    assert result2["data"] == {
        "email": "test-email",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.smarttub.config_flow.validate_credentials",
        autospec=True,
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "test-email", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_options(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        options={},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smarttub.config_flow.validate_credentials",
        autospec=True,
        return_value=True,
    ), patch("homeassistant.components.smarttub.async_setup", return_value=True), patch(
        "homeassistant.components.smarttub.async_setup_entry", return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.options == {}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
