"""Test the Flipr config flow."""

from unittest.mock import AsyncMock

import pytest
from requests.exceptions import HTTPError, Timeout

from homeassistant.components.flipr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_flipr_client: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_EMAIL: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flipr dummylogin"
    assert result["result"].unique_id == "dummylogin"
    assert result["data"] == {
        CONF_EMAIL: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (Exception("Bad request Boy :) --"), {"base": "unknown"}),
        (HTTPError, {"base": "invalid_auth"}),
        (Timeout, {"base": "cannot_connect"}),
        (ConnectionError, {"base": "cannot_connect"}),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_flipr_client: AsyncMock,
    exception: Exception,
    expected: dict[str, str],
) -> None:
    """Test we handle any error."""
    mock_flipr_client.search_all_ids.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_EMAIL: "nada",
            CONF_PASSWORD: "nadap",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected

    # Test of recover in normal state after correction of the 1st error
    mock_flipr_client.search_all_ids.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flipr dummylogin"
    assert result["data"] == {
        CONF_EMAIL: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }


async def test_no_flipr_found(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_flipr_client: AsyncMock
) -> None:
    """Test the case where there is no flipr found."""

    mock_flipr_client.search_all_ids.return_value = {"flipr": [], "hub": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_EMAIL: "nada",
            CONF_PASSWORD: "nadap",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_flipr_id_found"}

    # Test of recover in normal state after correction of the 1st error
    mock_flipr_client.search_all_ids.return_value = {"flipr": ["myfliprid"], "hub": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_EMAIL: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flipr dummylogin"
    assert result["data"] == {
        CONF_EMAIL: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }
