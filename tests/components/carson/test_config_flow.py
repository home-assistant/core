"""Test the Carson config flow."""
from asynctest import Mock, patch
from carson_living import CarsonAuthenticationError, CarsonCommunicationError

from homeassistant import config_entries, setup
from homeassistant.components.carson.const import CONF_LIST_FROM_EAGLE_EYE, DOMAIN

from .common import CONF_AND_FORM_CREDS

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
        "homeassistant.components.carson.config_flow.CarsonAuth",
        return_value=Mock(update_token=Mock(), token="test-token"),
    ), patch(
        "homeassistant.components.carson.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.carson.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONF_AND_FORM_CREDS,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == CONF_AND_FORM_CREDS["username"]
    assert result2["data"] == {
        "username": CONF_AND_FORM_CREDS["username"],
        "password": CONF_AND_FORM_CREDS["password"],
        "token": "test-token",
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
        "homeassistant.components.carson.config_flow.CarsonAuth.update_token",
        side_effect=CarsonAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONF_AND_FORM_CREDS,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.carson.config_flow.CarsonAuth.update_token",
        side_effect=CarsonCommunicationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONF_AND_FORM_CREDS,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_option_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    flow = await hass.config_entries.options.async_create_flow(
        entry.entry_id, context={"source": "test"}, data=None
    )

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "carson_devices"

    result = await flow.async_step_carson_devices(
        user_input={CONF_LIST_FROM_EAGLE_EYE: False}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_LIST_FROM_EAGLE_EYE: False,
    }
