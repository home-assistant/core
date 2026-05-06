"""Test the Litter-Robot config flow."""

from unittest.mock import PropertyMock, patch

from pylitterbot import Account
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .common import ACCOUNT_USER_ID, CONFIG, DOMAIN

from tests.common import MockConfigEntry

DHCP_DISCOVERY_LR4 = DhcpServiceInfo(
    ip="192.168.1.100",
    macaddress="aabbccddeeff",
    hostname="litter-robot4",
)
DHCP_DISCOVERY_LR5 = DhcpServiceInfo(
    ip="192.168.1.101",
    macaddress="aabbccddeef0",
    hostname="whiskerrobots",
)


async def test_full_flow(hass: HomeAssistant, mock_account) -> None:
    """Test full flow."""
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
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value=ACCOUNT_USER_ID,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[DOMAIN][CONF_USERNAME]
    assert result["data"] == CONFIG[DOMAIN]
    assert result["result"].unique_id == ACCOUNT_USER_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test already configured account is rejected before authentication."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONFIG[DOMAIN],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "connect_errors"),
    [
        (Exception, {"base": "unknown"}),
        (LitterRobotLoginException, {"base": "invalid_auth"}),
        (LitterRobotException, {"base": "cannot_connect"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant, mock_account, side_effect, connect_errors
) -> None:
    """Test creating an entry after error recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == connect_errors

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value=ACCOUNT_USER_ID,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[DOMAIN][CONF_USERNAME]
    assert result["data"] == CONFIG[DOMAIN]
    assert result["result"].unique_id == ACCOUNT_USER_ID


async def test_reauth(hass: HomeAssistant, mock_account: Account) -> None:
    """Test reauth flow (with fail and recover)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=LitterRobotLoginException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[DOMAIN][CONF_PASSWORD]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value=ACCOUNT_USER_ID,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[DOMAIN][CONF_PASSWORD]},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.unique_id == ACCOUNT_USER_ID
        assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauth flow aborts when credentials belong to a different account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
        ),
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value="different_user_id",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: CONFIG[DOMAIN][CONF_PASSWORD]},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == ACCOUNT_USER_ID
    assert entry.data == CONFIG[DOMAIN]


async def test_reconfigure(hass: HomeAssistant, mock_account: Account) -> None:
    """Test reconfiguration flow (with fail and recover)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    )
    entry.add_to_hass(hass)

    original_password = entry.data[CONF_PASSWORD]
    new_password = f"{original_password}_new"

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.litterrobot.config_flow.Account.connect",
        side_effect=LitterRobotLoginException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: new_password},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
        assert entry.data[CONF_PASSWORD] == original_password

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value=ACCOUNT_USER_ID,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: new_password},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.unique_id == ACCOUNT_USER_ID
        assert entry.data[CONF_PASSWORD] == new_password
        assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG[DOMAIN],
        unique_id=ACCOUNT_USER_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY_LR4,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_full_flow(
    hass: HomeAssistant, mock_account: Account
) -> None:
    """Test DHCP discovery through to successful entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY_LR4,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.connect",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.litterrobot.config_flow.Account.user_id",
            new_callable=PropertyMock,
            return_value=ACCOUNT_USER_ID,
        ),
        patch(
            "homeassistant.components.litterrobot.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[DOMAIN][CONF_USERNAME]
    assert result["data"] == CONFIG[DOMAIN]
    assert result["result"].unique_id == ACCOUNT_USER_ID
    assert len(mock_setup_entry.mock_calls) == 1
