"""Define tests for the triggercmd config flow."""

from unittest.mock import patch

import pytest
from triggercmd import TRIGGERcmdConnectionError

from homeassistant.components.triggercmd.const import CONF_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

invalid_token_with_length_100_or_more = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjEyMzQ1Njc4OTBxd2VydHl1aW9wYXNkZiIsImlhdCI6MTcxOTg4MTU4M30.E4T2S4RQfuI2ww74sUkkT-wyTGrV5_VDkgUdae5yo4E"
invalid_token_id = "1234567890qwertyuiopasdf"
invalid_token_with_length_100_or_more_and_no_id = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub2lkIjoiMTIzNDU2Nzg5MHF3ZXJ0eXVpb3Bhc2RmIiwiaWF0IjoxNzE5ODgxNTgzfQ.MaJLNWPGCE51Zibhbq-Yz7h3GkUxLurR2eoM2frnO6Y"


async def test_full_flow(
    hass: HomeAssistant,
) -> None:
    """Test config flow happy path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["errors"] == {}
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.triggercmd.client.async_connection_test",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.ha.Hub",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )

    assert result["data"] == {CONF_TOKEN: invalid_token_with_length_100_or_more}
    assert result["result"].unique_id == invalid_token_id
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (invalid_token_with_length_100_or_more_and_no_id, {"base": "unknown"}),
        ("not-a-token", {CONF_TOKEN: "invalid_token"}),
    ],
)
async def test_config_flow_user_invalid_token(
    hass: HomeAssistant,
    test_input: str,
    expected: dict,
) -> None:
    """Test the initial step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with (
        patch(
            "homeassistant.components.triggercmd.client.async_connection_test",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.ha.Hub",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: test_input},
        )

        assert result["errors"] == expected
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_entry_already_configured(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: invalid_token_with_length_100_or_more},
        unique_id=invalid_token_id,
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.triggercmd.client.async_connection_test",
            return_value=200,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )

    assert result["reason"] == "already_configured"
    assert result["type"] is FlowResultType.ABORT


async def test_config_flow_connection_error(hass: HomeAssistant) -> None:
    """Test a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with (
        patch(
            "homeassistant.components.triggercmd.client.async_connection_test",
            side_effect=TRIGGERcmdConnectionError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )

    assert result["errors"] == {
        "base": "cannot_connect",
    }
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.triggercmd.client.async_connection_test",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.ha.Hub",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
