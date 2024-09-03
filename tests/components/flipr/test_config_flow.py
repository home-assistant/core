"""Test the Flipr config flow."""

from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError, Timeout

from homeassistant import config_entries
from homeassistant.components.flipr.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(name="mock_setup")
def mock_setups():
    """Prevent setup."""
    with patch(
        "homeassistant.components.flipr.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER


async def test_invalid_credential(hass: HomeAssistant, mock_setup) -> None:
    """Test invalid credential."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids", side_effect=HTTPError()
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "bad_login",
                CONF_PASSWORD: "bad_pass",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_nominal_case(hass: HomeAssistant, mock_setup) -> None:
    """Test valid login form."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=["flipid"],
    ) as mock_flipr_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "dummylogin",
                CONF_PASSWORD: "dummypass",
            },
        )
        await hass.async_block_till_done()

    assert len(mock_flipr_client.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flipr dummylogin"
    assert result["data"] == {
        CONF_EMAIL: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }


async def test_no_flip_id(hass: HomeAssistant, mock_setup) -> None:
    """Test no flipr id found."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=[],
    ) as mock_flipr_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "dummylogin",
                CONF_PASSWORD: "dummypass",
            },
        )

        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_flipr_id_found"}

    assert len(mock_flipr_client.mock_calls) == 1


async def test_http_errors(hass: HomeAssistant, mock_setup) -> None:
    """Test HTTP Errors."""
    with patch("flipr_api.FliprAPIRestClient.search_flipr_ids", side_effect=Timeout()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "nada",
                CONF_PASSWORD: "nada",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        side_effect=Exception("Bad request Boy :) --"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "nada",
                CONF_PASSWORD: "nada",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
