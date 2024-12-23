"""Test the Playstation Network config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.playstation_network.config_flow import (
    PSNAWPAuthenticationError,
    PSNAWPException,
)
from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class mockUser:
    """Mock User class."""

    account_id = "1234"
    online_id = "testuser"


@pytest.mark.parametrize(
    ("npsso"),
    [
        ("TEST_NPSSO_TOKEN"),
        ('{"npsso": "TEST_NPSSO_TOKEN"}'),
    ],
)
async def test_form_success(hass: HomeAssistant, npsso) -> None:
    """Test we get the form."""
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
            {CONF_NPSSO: npsso},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NPSSO: "TEST_NPSSO_TOKEN",
    }


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPException(), "cannot_connect"),
        (PSNAWPAuthenticationError(), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_form_failures(hass: HomeAssistant, raise_error, text_error) -> None:
    """Test we handle a connection error."""
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
            data={CONF_NPSSO: "TEST_NPSSO_TOKEN"},
        )
        await hass.async_block_till_done()

    assert result["errors"] == {"base": text_error}
