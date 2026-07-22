"""Test the WATERCryst BIOCAT config flow."""

from unittest.mock import AsyncMock, patch

from httpx import HTTPStatusError, Request, RequestError, Response
from pyocat.models import DeviceResponse
import pytest

from homeassistant import config_entries
from homeassistant.components.watercryst.const import CONF_BSN, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api_client")
async def test_form_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schulungsgerät"
    assert result["data"] == {
        CONF_BSN: "2025001395300149",
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_api_client")
async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate entry handling."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="2025001395300149",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            HTTPStatusError(
                message="",
                request=Request(method="GET", url="v1/state"),
                response=Response(status_code=401),
            ),
            "invalid_auth",
        ),
        (
            HTTPStatusError(
                message="",
                request=Request(method="GET", url="v1/state"),
                response=Response(status_code=403),
            ),
            "api_disabled",
        ),
        (
            HTTPStatusError(
                message="",
                request=Request(method="GET", url="v1/state"),
                response=Response(status_code=500),
            ),
            "cannot_connect",
        ),
        (
            RequestError(
                message="",
                request=Request(method="GET", url="v1/state"),
            ),
            "cannot_connect",
        ),
        (Exception, "unknown"),
    ],
)
async def test_form_raise_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test an invalid setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_api_client.get_state.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api_client.get_state.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schulungsgerät"
    assert result["data"] == {
        CONF_BSN: "2025001395300149",
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_device_offline(
    hass: HomeAssistant, mock_api_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test with an offline device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_api_client.get_state.return_value.online = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_offline"}

    mock_api_client.get_state.return_value.online = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schulungsgerät"
    assert result["data"] == {
        CONF_BSN: "2025001395300149",
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_api_client")
async def test_form_wrong_device_serial(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test with an incorrect device serial."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "<wrong-bsn>",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_device_serial"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2025001395300149",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schulungsgerät"
    assert result["data"] == {
        CONF_BSN: "2025001395300149",
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_uses_bsn_as_title_when_name_is_none(
    hass: HomeAssistant,
) -> None:
    """Test the BIOCAT serial is used as title when the device has no name."""
    user_input = {
        CONF_BSN: "2025001395300149",
        CONF_API_KEY: "<api-key>",
    }

    with patch(
        "homeassistant.components.watercryst.config_flow.validate_input",
        new=AsyncMock(return_value=DeviceResponse(name=None)),
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "2025001395300149"
    assert result["data"] == user_input
    assert result["result"].unique_id == "2025001395300149"

    mock_validate_input.assert_awaited_once_with(hass, user_input)
