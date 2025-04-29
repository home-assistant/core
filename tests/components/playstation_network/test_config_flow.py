"""Test the Playstation Network config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.playstation_network.config_flow import (
    PSNAWPAuthenticationError,
    PSNAWPNotFound,
)
from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import NPSSO_TOKEN, PSN_ID

from tests.common import MockConfigEntry

MOCK_DATA_ADVANCED_STEP = {CONF_NPSSO: NPSSO_TOKEN}


class mockUser:
    """Mock User class."""

    account_id = PSN_ID
    online_id = "testuser"


@pytest.mark.parametrize(
    ("npsso"),
    [
        ("TEST_NPSSO_TOKEN"),
        ('{"npsso": "TEST_NPSSO_TOKEN"}'),
    ],
)
async def test_manual_config(hass: HomeAssistant, npsso) -> None:
    """Test creating via manual configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.playstation_network.config_flow.PlaystationNetwork.get_user",
        return_value=mockUser(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NPSSO: npsso},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "my-psn-id"
    assert result["data"] == {
        CONF_NPSSO: "TEST_NPSSO_TOKEN",
    }


async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort form login when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.playstation_network.config_flow.PlaystationNetwork.get_user",
        return_value=mockUser(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NPSSO: NPSSO_TOKEN},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPNotFound(), "invalid_account"),
        (PSNAWPAuthenticationError(), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_form_failures(hass: HomeAssistant, raise_error, text_error) -> None:
    """Test we handle a connection error.

    First we generate an error and after fixing it, we are still able to submit.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.playstation_network.config_flow.PlaystationNetwork.get_user",
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_NPSSO: NPSSO_TOKEN},
        )

    assert result["errors"] == {"base": text_error}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.playstation_network.config_flow.PlaystationNetwork.get_user",
        return_value=mockUser(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NPSSO: NPSSO_TOKEN},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NPSSO: NPSSO_TOKEN,
    }
