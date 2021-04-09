"""Test the sia config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sia.const import DOMAIN

BASIC_CONFIG = {
    "port": 7777,
    "protocol": "TCP",
    "account": "ABCDEF",
    "encryption_key": "AAAAAAAAAAAAAAAA",
    "ping_interval": 10,
    "zones": 1,
    "ignore_timestamps": False,
    "additional_account": False,
}

ADDITIONAL_ACCOUNT = {
    "account": "ACC2",
    "encryption_key": "AAAAAAAAAAAAAAAA",
    "ping_interval": 2,
    "zones": 2,
    "ignore_timestamps": False,
    "additional_account": False,
}


async def test_form(hass):
    """Test we get the form."""
    with patch(
        "homeassistant.components.sia.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sia.config_flow.validate_input",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=BASIC_CONFIG,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"SIA Alarm on port {BASIC_CONFIG['port']}"
        assert result["data"] == {
            "port": BASIC_CONFIG["port"],
            "protocol": BASIC_CONFIG["protocol"],
            "accounts": [
                {
                    "account": BASIC_CONFIG["account"],
                    "encryption_key": BASIC_CONFIG["encryption_key"],
                    "ping_interval": BASIC_CONFIG["ping_interval"],
                    "zones": BASIC_CONFIG["zones"],
                    "ignore_timestamps": BASIC_CONFIG["ignore_timestamps"],
                }
            ],
        }


async def test_form_additional_account(hass):
    """Test we handle invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    config = BASIC_CONFIG.copy()
    config["additional_account"] = True
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.sia.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sia.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], ADDITIONAL_ACCOUNT
        )
    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "SIA Alarm on port 7777"
    assert result3["data"] == {
        "port": 7777,
        "protocol": "TCP",
        "accounts": [
            {
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 10,
                "zones": 1,
                "ignore_timestamps": False,
            },
            {
                "account": "ACC2",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 2,
                "zones": 2,
                "ignore_timestamps": False,
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
    await hass.config_entries.flow.async_configure(result["flow_id"], BASIC_CONFIG)

    result_abort = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result3 = await hass.config_entries.flow.async_configure(
        result_abort["flow_id"], BASIC_CONFIG
    )
    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


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
    assert result_err["type"] == "form"
    assert result_err["errors"] == {"base": error}
