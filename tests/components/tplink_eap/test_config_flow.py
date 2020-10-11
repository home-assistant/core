"""Test the TP-Link EAP config flow."""
from pytleap.error import AuthenticationError, CommunicationError

from homeassistant import config_entries, setup
from homeassistant.components.tplink_eap.const import DOMAIN
from homeassistant.const import CONF_URL

from tests.async_mock import PropertyMock, patch
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
        "homeassistant.components.tplink_eap.config_flow.Eap.connect",
        return_value=None,
    ), patch(
        "homeassistant.components.tplink_eap.config_flow.Eap.disconnect",
        return_value=None,
    ), patch(
        "homeassistant.components.tplink_eap.config_flow.Eap.name",
        new_callable=PropertyMock,
    ) as mock_name, patch(
        "homeassistant.components.tplink_eap.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.tplink_eap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_name.return_value = "My AP"
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://localhost",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "TP-Link EAP My AP"
    assert result2["data"] == {
        "url": "http://localhost",
        "username": "test-username",
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
        "homeassistant.components.tplink_eap.config_flow.Eap.connect",
        side_effect=AuthenticationError("Authentication invalid or expired"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://localhost",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tplink_eap.config_flow.Eap.connect",
        side_effect=CommunicationError("Cannot connect to localhost"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://localhost",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_repeat_identifier(hass):
    """Test we handle repeat identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        data={CONF_URL: "http://localhost"},
        options=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "http://localhost",
            "username": "test-username",
            "password": "test-password",
        },
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
