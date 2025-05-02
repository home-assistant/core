"""Test the Playstation Network config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.playstation_network.config_flow import (
    PSNAWPAuthenticationError,
    PSNAWPInvalidTokenError,
    PSNAWPNotFoundError,
)
from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import NPSSO_TOKEN, NPSSO_TOKEN_INVALID_JSON, PSN_ID

from tests.common import MockConfigEntry

MOCK_DATA_ADVANCED_STEP = {CONF_NPSSO: NPSSO_TOKEN}


async def test_manual_config(hass: HomeAssistant, mock_psnawpapi: MagicMock) -> None:
    """Test creating via manual configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "TEST_NPSSO_TOKEN"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == PSN_ID
    assert result["data"] == {
        CONF_NPSSO: "TEST_NPSSO_TOKEN",
    }


async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test we abort form login when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPNotFoundError(), "invalid_account"),
        (PSNAWPAuthenticationError(), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_form_failures(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test we handle a connection error.

    First we generate an error and after fixing it, we are still able to submit.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_psnawpapi.get_user.side_effect = raise_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["errors"] == {"base": text_error}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_psnawpapi.get_user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NPSSO: NPSSO_TOKEN,
    }


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPInvalidTokenError(), "invalid_account"),
    ],
)
async def test_parse_npsso_token_failures(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test parse_npsso_token raises the correct exceptions during config flow."""
    with patch(
        "psnawp_api.utils.misc.parse_npsso_token",
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_init(
            "playstation_network", context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NPSSO: NPSSO_TOKEN_INVALID_JSON}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": text_error}

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NPSSO: NPSSO_TOKEN},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_NPSSO: NPSSO_TOKEN,
        }
