"""Test the nuki config flow."""
from unittest.mock import patch

from pynuki.bridge import InvalidCredentialsException
from requests.exceptions import RequestException

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.nuki.const import DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    mock_info = {"ids": {"hardwareId": "0001"}}

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.nuki.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nuki.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
                "token": "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "0001"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 8080,
        "token": "test-token",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test that the import works."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_info = {"ids": {"hardwareId": "0001"}}

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.nuki.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nuki.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "1.1.1.1", "port": 8080, "token": "test-token"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "0001"
        assert result["data"] == {
            "host": "1.1.1.1",
            "port": 8080,
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
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=InvalidCredentialsException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
                "token": "test-token",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=RequestException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
                "token": "test-token",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
                "token": "test-token",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain="nuki",
        unique_id="0001",
        data={"host": "1.1.1.1", "port": 8080, "token": "test-token"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        return_value={"ids": {"hardwareId": "0001"}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
                "token": "test-token",
            },
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "already_configured"
