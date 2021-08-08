"""Test the Uptime Robot config flow."""
from unittest.mock import patch

from pytest import LogCaptureFixture
from pyuptimerobot import UptimeRobotApiResponse
from pyuptimerobot.exceptions import (
    UptimeRobotAuthenticationException,
    UptimeRobotException,
)

from homeassistant import config_entries
from homeassistant.components.uptimerobot.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

    assert result2["result"].unique_id == "1234567890"
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test@test.test"
    assert result2["data"] == {"api_key": "1234"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        side_effect=UptimeRobotException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )

    assert result2["errors"]["base"] == "unknown"


async def test_form_api_key_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        side_effect=UptimeRobotAuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )

    assert result2["errors"]["base"] == "invalid_api_key"


async def test_form_api_error(hass: HomeAssistant, caplog: LogCaptureFixture) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "fail",
                "error": {"message": "test error from API."},
            }
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )

    assert result2["errors"]["base"] == "unknown"
    assert "test error from API." in caplog.text


async def test_flow_import(hass):
    """Test an import flow."""
    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"platform": DOMAIN, "api_key": "1234"},
        )
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {"api_key": "1234"}

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"platform": DOMAIN, "api_key": "1234"},
        )
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict({"stat": "ok"}),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"platform": DOMAIN, "api_key": "12345"},
        )
        await hass.async_block_till_done()

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "unknown"


async def test_user_unique_id_already_exists(hass):
    """Test creating an entry where the unique_id already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "12345"},
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0
    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_reauthentication(hass):
    """Test Uptime Robot reauthentication."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=old_entry.data,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauthentication_failure(hass):
    """Test Uptime Robot reauthentication failure."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=old_entry.data,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "fail",
                "error": {"message": "test error from API."},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"]["base"] == "unknown"


async def test_reauthentication_failure_no_existing_entry(hass):
    """Test Uptime Robot reauthentication with no existing entry."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"platform": DOMAIN, "api_key": "1234"},
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=old_entry.data,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567890},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_failed_existing"


async def test_reauthentication_failure_account_not_matching(hass):
    """Test Uptime Robot reauthentication failure when using another account."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"platform": DOMAIN, "api_key": "1234"},
        unique_id="1234567890",
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "unique_id": "1234567890"},
        data=old_entry.data,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_account_details",
        return_value=UptimeRobotApiResponse.from_dict(
            {
                "stat": "ok",
                "account": {"email": "test@test.test", "user_id": 1234567891},
            }
        ),
    ), patch(
        "homeassistant.components.uptimerobot.async_setup_entry",
        return_value=True,
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "1234"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"]["base"] == "reauth_failed_matching_account"
