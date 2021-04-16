"""Test the kmtronic config flow."""
from unittest.mock import Mock, patch

from aiohttp import ClientConnectorError, ClientResponseError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.kmtronic.const import CONF_REVERSE, DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED

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
        "homeassistant.components.kmtronic.config_flow.KMTronicHubAPI.async_get_status",
        return_value=[Mock()],
    ), patch(
        "homeassistant.components.kmtronic.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kmtronic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_options(hass, aioclient_mock):
    """Test that the options form."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "admin",
            "password": "admin",
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_REVERSE: True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {CONF_REVERSE: True}

    await hass.async_block_till_done()

    assert config_entry.state == "loaded"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kmtronic.config_flow.KMTronicHubAPI.async_get_status",
        side_effect=ClientResponseError(None, None, status=401),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
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
        "homeassistant.components.kmtronic.config_flow.KMTronicHubAPI.async_get_status",
        side_effect=ClientConnectorError(None, Mock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kmtronic.config_flow.KMTronicHubAPI.async_get_status",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
