"""Test the UptimeRobot config flow."""

from unittest.mock import patch

import pytest
from pyuptimerobot import UptimeRobotAuthenticationException, UptimeRobotException

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    MOCK_UPTIMEROBOT_ACCOUNT,
    MOCK_UPTIMEROBOT_API_KEY,
    MOCK_UPTIMEROBOT_API_KEY_READ_ONLY,
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA,
    MOCK_UPTIMEROBOT_UNIQUE_ID,
    MockApiResponseKey,
    mock_uptimerobot_api_response,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ACCOUNT),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )
        await hass.async_block_till_done()

    assert result2["result"].unique_id == MOCK_UPTIMEROBOT_UNIQUE_ID
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_UPTIMEROBOT_ACCOUNT["email"]
    assert result2["data"] == {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_read_only(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ACCOUNT),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY_READ_ONLY},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "not_main_key"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (Exception, "unknown"),
        (UptimeRobotException, "cannot_connect"),
        (UptimeRobotAuthenticationException, "invalid_api_key"),
    ],
)
async def test_form_exception_thrown(hass: HomeAssistant, exception, error_key) -> None:
    """Test that we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == error_key


async def test_form_api_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ERROR),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )

    assert result2["errors"]["base"] == "unknown"
    assert "test error from API." in caplog.text


async def test_user_unique_id_already_exists(
    hass: HomeAssistant,
) -> None:
    """Test creating an entry where the unique_id already exists."""
    entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ACCOUNT),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "12345"},
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauthentication(
    hass: HomeAssistant,
) -> None:
    """Test UptimeRobot reauthentication."""
    old_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ACCOUNT),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauthentication_failure(
    hass: HomeAssistant,
) -> None:
    """Test UptimeRobot reauthentication failure."""
    old_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ERROR),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"


async def test_reauthentication_failure_no_existing_entry(
    hass: HomeAssistant,
) -> None:
    """Test UptimeRobot reauthentication with no existing entry."""
    old_entry = MockConfigEntry(
        **{**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA, "unique_id": None}
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ACCOUNT),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_failed_existing"


async def test_reauthentication_failure_account_not_matching(
    hass: HomeAssistant,
) -> None:
    """Test UptimeRobot reauthentication failure when using another account."""
    old_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_account_details",
            return_value=mock_uptimerobot_api_response(
                key=MockApiResponseKey.ACCOUNT,
                data={**MOCK_UPTIMEROBOT_ACCOUNT, "user_id": 1234567891},
            ),
        ),
        patch(
            "homeassistant.components.uptimerobot.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: MOCK_UPTIMEROBOT_API_KEY},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "reauth_failed_matching_account"
