"""Test the Fresh-r config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from pyfreshr.exceptions import LoginError

from homeassistant import config_entries
from homeassistant.components.freshr.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}


def _mock_client(login_side_effect=None):
    """Return a mocked FreshrClient."""
    client = MagicMock()
    client.login = AsyncMock(side_effect=login_side_effect)
    client.close = AsyncMock()
    return client


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Fresh-r (test-username)"
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow handles invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(login_side_effect=LoginError("bad credentials")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # Ensure it can recover after correct credentials
    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow handles unexpected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(login_side_effect=RuntimeError("unexpected")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow handles connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(login_side_effect=ClientError("network")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Ensure it can recover after the network is OK
    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow aborts when the account is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_INPUT[CONF_USERNAME],
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.freshr.config_flow.FreshrClient",
        return_value=_mock_client(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
