"""Test the Litter-Robot config flow."""

from unittest.mock import patch

from pylitterbot import Account
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant import config_entries
from homeassistant.components import litterrobot
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import CONF_USERNAME, CONFIG, DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_account) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[DOMAIN][CONF_USERNAME]
    assert result2["data"] == CONFIG[DOMAIN]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured."""
    MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONFIG[litterrobot.DOMAIN],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=LitterRobotLoginException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=LitterRobotException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_step_reauth(hass: HomeAssistant, mock_account: Account) -> None:
    """Test the reauth flow."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[litterrobot.DOMAIN][CONF_PASSWORD]},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_step_reauth_failed(hass: HomeAssistant, mock_account: Account) -> None:
    """Test the reauth flow fails and recovers."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=LitterRobotLoginException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[litterrobot.DOMAIN][CONF_PASSWORD]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[litterrobot.DOMAIN][CONF_PASSWORD]},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert len(mock_setup_entry.mock_calls) == 1
