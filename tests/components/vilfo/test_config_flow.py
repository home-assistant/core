"""Test the Vilfo Router config flow."""
from unittest.mock import Mock, patch

import vilfo

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.vilfo.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_ID, CONF_MAC


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_mac = "FF-00-00-00-00-00"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.get_board_information", return_value=None
    ), patch("vilfo.Client.resolve_mac_address", return_value=mock_mac), patch(
        "homeassistant.components.vilfo.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.vilfo.async_setup_entry"
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "testadmin.vilfo.com", CONF_ACCESS_TOKEN: "test-token"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "testadmin.vilfo.com"
    assert result2["data"] == {
        "host": "testadmin.vilfo.com",
        "access_token": "test-token",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.resolve_mac_address", return_value=None
    ), patch(
        "vilfo.Client.get_board_information",
        side_effect=vilfo.exceptions.AuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "testadmin.vilfo.com", "access_token": "test-token"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("vilfo.Client.ping", side_effect=vilfo.exceptions.VilfoException), patch(
        "vilfo.Client.resolve_mac_address"
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "testadmin.vilfo.com", "access_token": "test-token"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch("vilfo.Client.ping", side_effect=vilfo.exceptions.VilfoException), patch(
        "vilfo.Client.resolve_mac_address"
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "testadmin.vilfo.com", "access_token": "test-token"},
        )

    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_wrong_host(hass):
    """Test we handle wrong host errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"host": "this is an invalid hostname", "access_token": "test-token"},
    )

    assert result["errors"] == {"host": "wrong_host"}


async def test_form_already_configured(hass):
    """Test that we handle already configured exceptions appropriately."""
    first_flow_result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.get_board_information",
        return_value=None,
    ), patch("vilfo.Client.resolve_mac_address", return_value=None):
        first_flow_result2 = await hass.config_entries.flow.async_configure(
            first_flow_result1["flow_id"],
            {CONF_HOST: "testadmin.vilfo.com", CONF_ACCESS_TOKEN: "test-token"},
        )

    second_flow_result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.get_board_information",
        return_value=None,
    ), patch("vilfo.Client.resolve_mac_address", return_value=None):
        second_flow_result2 = await hass.config_entries.flow.async_configure(
            second_flow_result1["flow_id"],
            {CONF_HOST: "testadmin.vilfo.com", CONF_ACCESS_TOKEN: "test-token"},
        )

    assert first_flow_result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert second_flow_result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert second_flow_result2["reason"] == "already_configured"


async def test_form_unexpected_exception(hass):
    """Test that we handle unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vilfo.config_flow.VilfoClient",
    ) as mock_client:
        mock_client.return_value.ping = Mock(side_effect=Exception)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "testadmin.vilfo.com", "access_token": "test-token"},
        )

    assert result2["errors"] == {"base": "unknown"}


async def test_validate_input_returns_data(hass):
    """Test we handle the MAC address being resolved or not."""
    mock_data = {"host": "testadmin.vilfo.com", "access_token": "test-token"}
    mock_data_with_ip = {"host": "192.168.0.1", "access_token": "test-token"}
    mock_mac = "FF-00-00-00-00-00"

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.get_board_information", return_value=None
    ), patch("vilfo.Client.resolve_mac_address", return_value=None):
        result = await hass.components.vilfo.config_flow.validate_input(
            hass, data=mock_data
        )

    assert result["title"] == mock_data["host"]
    assert result[CONF_HOST] == mock_data["host"]
    assert result[CONF_MAC] is None
    assert result[CONF_ID] == mock_data["host"]

    with patch("vilfo.Client.ping", return_value=None), patch(
        "vilfo.Client.get_board_information", return_value=None
    ), patch("vilfo.Client.resolve_mac_address", return_value=mock_mac):
        result2 = await hass.components.vilfo.config_flow.validate_input(
            hass, data=mock_data
        )
        result3 = await hass.components.vilfo.config_flow.validate_input(
            hass, data=mock_data_with_ip
        )

    assert result2["title"] == mock_data["host"]
    assert result2[CONF_HOST] == mock_data["host"]
    assert result2[CONF_MAC] == mock_mac
    assert result2[CONF_ID] == mock_mac

    assert result3["title"] == mock_data_with_ip["host"]
    assert result3[CONF_HOST] == mock_data_with_ip["host"]
    assert result3[CONF_MAC] == mock_mac
    assert result3[CONF_ID] == mock_mac
