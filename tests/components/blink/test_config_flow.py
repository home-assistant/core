"""Test the Blink config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.blink import DOMAIN

from tests.async_mock import Mock, patch
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
        "homeassistant.components.blink.config_flow.Blink",
        return_value=Mock(
            get_auth_token=Mock(return_value=True),
            key_required=False,
            login_response={},
        ),
    ), patch(
        "homeassistant.components.blink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "blink"
    assert result2["result"].unique_id == "blink@example.com"
    assert result2["data"] == {
        "username": "blink@example.com",
        "password": "example",
        "login_response": {},
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test we import the config."""
    with patch(
        "homeassistant.components.blink.config_flow.Blink",
        return_value=Mock(
            get_auth_token=Mock(return_value=True),
            key_required=False,
            login_response={},
        ),
    ), patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "username": "blink@example.com",
                "password": "example",
                "scan_interval": 10,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "blink"
    assert result["result"].unique_id == "blink@example.com"
    assert result["data"] == {
        "username": "blink@example.com",
        "password": "example",
        "scan_interval": 10,
        "login_response": {},
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_2fa(hass):
    """Test we get the 2fa form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_blink = Mock(
        get_auth_token=Mock(return_value=True),
        key_required=True,
        login_response={},
        login_handler=Mock(send_auth_key=Mock(return_value=True)),
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink", return_value=mock_blink
    ), patch(
        "homeassistant.components.blink.async_setup", return_value=True
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "2fa"

    mock_blink.key_required = False
    with patch(
        "homeassistant.components.blink.config_flow.Blink", return_value=mock_blink
    ), patch(
        "homeassistant.components.blink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == "blink"
    assert result3["result"].unique_id == "blink@example.com"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.get_auth_token",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass):
    """Test we handle unknown error at startup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.get_auth_token",
        return_value=None,
    ), patch(
        "homeassistant.components.blink.config_flow.validate_input",
        side_effect=KeyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "blink@example.com",
            "password": "example",
            "login_response": {},
        },
        options={},
        entry_id=1,
    )
    config_entry.add_to_hass(hass)

    mock_blink = Mock(
        login_handler=True,
        setup_params=Mock(return_value=True),
        setup_post_verify=Mock(return_value=True),
    )

    with patch("homeassistant.components.blink.Blink", return_value=mock_blink):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "simple_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 5},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {"scan_interval": 5}
    assert mock_blink.refresh_rate == 5
