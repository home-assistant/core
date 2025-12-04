"""Test the Rituals Perfume Genie config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from pyrituals import AuthenticationException

from homeassistant.components.rituals_perfume_genie.const import ACCOUNT_HASH, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_EMAIL = "test@rituals.com"
TEST_PASSWORD = "test-password"


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user flow setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.rituals_perfume_genie.config_flow.Account"
        ) as mock_account_cls,
        patch(
            "homeassistant.components.rituals_perfume_genie.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_account = mock_account_cls.return_value
        mock_account.authenticate = AsyncMock()
        mock_account.account_hash = "mock_hash"
        mock_account.email = TEST_EMAIL

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_EMAIL
    assert result2["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert ACCOUNT_HASH not in result2["data"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test user flow with invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rituals_perfume_genie.config_flow.Account"
    ) as mock_account_cls:
        mock_account = mock_account_cls.return_value
        mock_account.authenticate = AsyncMock(side_effect=AuthenticationException)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rituals_perfume_genie.config_flow.Account"
    ) as mock_account_cls:
        mock_account = mock_account_cls.return_value
        mock_account.authenticate = AsyncMock(side_effect=ClientError)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test successful reauth flow (updating credentials)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_hash",
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: "wrong_password",
            ACCOUNT_HASH: "old_hash_should_be_removed",
        },
    )
    entry.add_to_hass(hass)

    # Reauth
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.rituals_perfume_genie.config_flow.Account"
        ) as mock_account_cls,
        patch(
            "homeassistant.components.rituals_perfume_genie.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_account = mock_account_cls.return_value
        mock_account.authenticate = AsyncMock()
        mock_account.account_hash = "mock_hash"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new_correct_password",
                CONF_EMAIL: TEST_EMAIL,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert entry.data[CONF_PASSWORD] == "new_correct_password"
    assert ACCOUNT_HASH not in entry.data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_auth_error(hass: HomeAssistant) -> None:
    """Test reauth flow with authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.rituals_perfume_genie.config_flow.Account"
    ) as mock_account_cls:
        mock_account = mock_account_cls.return_value
        mock_account.authenticate = AsyncMock(side_effect=AuthenticationException)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "still_wrong_password",
                CONF_EMAIL: TEST_EMAIL,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
