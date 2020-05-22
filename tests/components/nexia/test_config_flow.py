"""Test the nexia config flow."""
from requests.exceptions import ConnectTimeout

from homeassistant import config_entries, setup
from homeassistant.components.nexia.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import MagicMock, patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
        return_value="myhouse",
    ), patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=MagicMock(),
    ), patch(
        "homeassistant.components.nexia.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nexia.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "myhouse"
    assert result2["data"] == {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.nexia.config_flow.NexiaHome.login"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=ConnectTimeout,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
        return_value="myhouse",
    ), patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=MagicMock(),
    ), patch(
        "homeassistant.components.nexia.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nexia.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "myhouse"
    assert result["data"] == {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_USERNAME: "username", CONF_PASSWORD: "password"},
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
