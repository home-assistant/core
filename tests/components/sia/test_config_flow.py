"""Test the sia config flow."""
from asynctest import patch
from pysiaalarm.sia_errors import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
    PortInUseError,
)

from homeassistant import config_entries, setup
from homeassistant.components.sia.config_flow import InvalidPing
from homeassistant.components.sia.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sia.config_flow.validate_input", return_value=True,
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

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=InvalidKeyFormatError,
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

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_key_format"}


async def test_form_invalid_key_length(hass):
    """Test we handle invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=InvalidKeyLengthError,
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

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_key_length"}


async def test_form_invalid_account_format(hass):
    """Test we handle invalid account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=InvalidAccountFormatError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 7777,
                "account": "A",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_account_format"}


async def test_form_invalid_account_length(hass):
    """Test we handle invalid account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=InvalidAccountLengthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 7777,
                "account": "A",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_account_length"}


async def test_form_invalid_ping(hass):
    """Test we handle invalid ping."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=InvalidPing,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 7777,
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 1500,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_ping"}


async def test_form_port_in_use(hass):
    """Test we handle port in use."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sia.config_flow.validate_input",
        side_effect=PortInUseError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "SIA",
                "port": 80,
                "account": "ABCDEF",
                "encryption_key": "AAAAAAAAAAAAAAAA",
                "ping_interval": 10,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "port_in_use"}
