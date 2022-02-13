"""Test the IntelliFire config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from intellifire4py.control import LoginException

from homeassistant import config_entries
from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.components.intellifire.conftest import mock_api_connection_error


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireControlAsync",
    login=AsyncMock(),
    get_username=AsyncMock(return_value="intellifire"),
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "intelli",
            "password": "fire",
            "ssl": True,
            "verify_ssl": True,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_local(
    hass: HomeAssistant, mock_intellifire_config_flow_with_local_error: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    # mock_intellifire_config_flow_with_local_error.poll.side_effect = ConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "intelli",
            "password": "fire",
            "ssl": True,
            "verify_ssl": True,
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireControlAsync",
    login=AsyncMock(side_effect=mock_api_connection_error()),
    get_username=AsyncMock(
        return_value="intellifire",
    ),
)
async def test_form_api_connect_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "intelli",
            "password": "fire",
            "ssl": True,
            "verify_ssl": True,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "iftapi_connect"}


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireControlAsync",
    login=AsyncMock(side_effect=LoginException()),
)
async def test_form_api_login_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "intelli",
            "password": "fire",
            "ssl": True,
            "verify_ssl": True,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "api_error"}
