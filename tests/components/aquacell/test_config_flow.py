"""Test the Aquacell config flow."""

import string
from unittest.mock import AsyncMock, patch

from aioaquacell import ApiException, AuthenticationFailed
import pytest

from homeassistant import config_entries
from homeassistant.components.aquacell.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.aquacell import TEST_RESULT_DATA, TEST_USER_INPUT

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def __mock_authenticate(self, user_name, password) -> string:
    return "refresh-token"


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        __mock_authenticate,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@test.com"
    assert result2["data"] == {**TEST_RESULT_DATA}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_reauth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the reauth step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        __mock_authenticate,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["data"] == {**TEST_RESULT_DATA}

        assert len(mock_setup_entry.mock_calls) == 1

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH},
            data=TEST_USER_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=AuthenticationFailed,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@test.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=ApiException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@test.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@test.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_exceptions(hass: HomeAssistant) -> None:
    """Test we handle exceptions during reauthentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    # Test reauth but the entry doesn't exist
    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        __mock_authenticate,
    ):
        fake_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert fake_result["type"] == FlowResultType.CREATE_ENTRY
        assert fake_result["title"] == TEST_USER_INPUT[CONF_EMAIL]
        assert fake_result["data"] == TEST_RESULT_DATA

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=TEST_USER_INPUT
    )

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=AuthenticationFailed,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.aquacell.config_flow.AquacellApi.authenticate",
        side_effect=ApiException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
