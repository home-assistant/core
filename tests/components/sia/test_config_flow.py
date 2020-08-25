"""Test the sia config flow."""
from asynctest import patch
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.sia.const import DOMAIN
from homeassistant.data_entry_flow import AbortFlow

BASIC_CONFIG = {
    "port": 7777,
    "account": "ABCDEF",
    "encryption_key": "AAAAAAAAAAAAAAAA",
    "ping_interval": 10,
    "zones": 1,
    "additional_account": False,
}

ADDITIONAL_ACCOUNT = {
    "account": "ACC2",
    "encryption_key": "AAAAAAAAAAAAAAAA",
    "ping_interval": 2,
    "zones": 2,
    "additional_account": False,
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sia.config_flow.validate_input", return_value={},
    ), patch(
        "homeassistant.components.sia.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sia.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 7777,
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ABCDEF"
    assert result2["data"] == {
        "name": "SIA",
        "port": 7777,
        "account": "ABCDEF",
        "encryption_key": "AAAAAAAAAAAAAAAA",
        "ping_interval": 10,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_key_format(hass):
    """Test we handle invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    config = BASIC_CONFIG.copy()
    config["additional_account"] = True
    print(config)
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "form"
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.sia.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sia.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], ADDITIONAL_ACCOUNT
        )
    assert result3["type"] == "create_entry"
    assert result3["title"] == "SIA Alarm on port 7777"
    assert result3["data"] == {
        "port": 7777,
        "accounts": [
            {
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        ],
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_form(hass):
    """Test we handle invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.config_entries.ConfigFlow._abort_if_unique_id_configured",
        side_effect=AbortFlow(reason="already_configured"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 7777,
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    "additional, field, value, error",
    [
        (False, "encryption_key", "AAAAAAAAAAAAAZZZ", "invalid_key_format"),
        (True, "encryption_key", "AAAAAAAAAAAAAZZZ", "invalid_key_format"),
        (False, "encryption_key", "AAAAAAAAAAAAA", "invalid_key_length"),
        (True, "encryption_key", "AAAAAAAAAAAAA", "invalid_key_length"),
        (False, "account", "ZZZ", "invalid_account_format"),
        (True, "account", "ZZZ", "invalid_account_format"),
        (False, "account", "A", "invalid_account_length"),
        (True, "account", "A", "invalid_account_length"),
        (False, "ping_interval", 1500, "invalid_ping"),
        (True, "ping_interval", 1500, "invalid_ping"),
        (False, "zones", 0, "invalid_zones"),
        (True, "zones", 0, "invalid_zones"),
    ],
)
async def test_form_errors(hass, additional, field, value, error):
    """Test we handle the different invalid inputs, both in the main and in the additional flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    if not additional:
        config = BASIC_CONFIG.copy()
        config[field] = value
    else:
        add_config = BASIC_CONFIG.copy()
        add_config["additional_account"] = True
        result_add = await hass.config_entries.flow.async_configure(
            result["flow_id"], add_config
        )
        assert result_add["type"] == "form"
        assert result_add["errors"] == {}

        config = ADDITIONAL_ACCOUNT.copy()
        config[field] = value

    with patch("homeassistant.components.sia.async_setup_entry", return_value=True):
        result_err = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
    print(result_err)
    assert result_err["type"] == "form"
    assert result_err["errors"] == {"base": error}
