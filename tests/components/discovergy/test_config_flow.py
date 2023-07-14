"""Test the Discovergy config flow."""
from unittest.mock import Mock, patch

from pydiscovergy.error import HTTPError, InvalidLogin

from homeassistant import data_entry_flow
from homeassistant.components.discovergy.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_meters: Mock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(
    hass: HomeAssistant, mock_meters: Mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": mock_config_entry.unique_id},
        data=None,
    )

    assert init_result["type"] == data_entry_flow.FlowResultType.FORM
    assert init_result["step_id"] == "reauth"

    with patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

        assert configure_result["type"] == data_entry_flow.FlowResultType.ABORT
        assert configure_result["reason"] == "reauth_successful"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pydiscovergy.Discovergy.get_meters",
        side_effect=InvalidLogin,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pydiscovergy.Discovergy.get_meters", side_effect=HTTPError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pydiscovergy.Discovergy.get_meters", side_effect=Exception):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
