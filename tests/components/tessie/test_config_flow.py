"""Test the Tessie config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.tessie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_DATA,
    TEST_VEHICLES,
    URL_VEHICLES,
    setup_platform,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test we get the form."""

    aioclient_mock.get(
        URL_VEHICLES,
        text=TEST_VEHICLES,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert not result1["errors"]

    with patch(
        "homeassistant.components.tessie.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Tessie"
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_access_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid auth is handled."""

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_AUTH,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_DATA,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_access_token"}


async def test_form_invalid_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid auth is handled."""

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_DATA,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_network_issue(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test network issues are handled."""

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_CONNECTION,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        TEST_DATA,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test reauth flow."""

    aioclient_mock.get(
        URL_VEHICLES,
        text=TEST_VEHICLES,
    )
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id="abc",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_DATA,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == TEST_DATA


async def test_reauth_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow that fails."""
    mock_entry = await setup_platform(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_DATA,
    )

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_AUTH,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_access_token"}

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )


async def test_reauth_error_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow that fails."""
    mock_entry = await setup_platform(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_DATA,
    )

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )


async def test_reauth_error_connection(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow that fails."""
    mock_entry = await setup_platform(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=TEST_DATA,
    )

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_CONNECTION,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )
