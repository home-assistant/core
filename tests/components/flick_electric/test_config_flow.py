"""Test the Flick Electric config flow."""

from unittest.mock import AsyncMock, patch

from pyflick.authentication import AuthException
from pyflick.types import APIException

from homeassistant import config_entries
from homeassistant.components.flick_electric.const import (
    CONF_ACCOUNT_ID,
    CONF_SUPPLY_NODE_REF,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF, setup_integration

from tests.common import MockConfigEntry

# From test fixtures
ACCOUNT_NAME_1 = "123 Fake Street, Newtown, Wellington 6021"
ACCOUNT_NAME_2 = "456 Fake Street, Newtown, Wellington 6021"
ACCOUNT_ID_2 = "123456"
SUPPLY_NODE_REF_2 = "/network/nz/supply_nodes/ed7617df-4b10-4c8a-a05d-deadbeef1234"


async def _flow_submit(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
    )


async def test_form(hass: HomeAssistant, mock_flick_client: AsyncMock) -> None:
    """Test we get the form with only one, with no account picker."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == ACCOUNT_NAME_1
    assert result2["data"] == CONF
    assert result2["result"].unique_id == CONF[CONF_ACCOUNT_ID]


async def test_form_multi_account(
    hass: HomeAssistant, mock_flick_client_multiple: AsyncMock
) -> None:
    """Test the form when multiple accounts are available."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_account"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_ACCOUNT_ID: ACCOUNT_ID_2},
    )

    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == ACCOUNT_NAME_2
    assert result3["data"] == {
        **CONF,
        CONF_SUPPLY_NODE_REF: SUPPLY_NODE_REF_2,
        CONF_ACCOUNT_ID: ACCOUNT_ID_2,
    }
    assert result3["result"].unique_id == ACCOUNT_ID_2


async def test_reauth_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test reauth flow when username/password is wrong."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=AuthException,
    ):
        result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: CONF[CONF_USERNAME], CONF_PASSWORD: CONF[CONF_PASSWORD]},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_form_reauth_migrate(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test reauth flow for v1 with single account."""
    mock_old_config_entry.add_to_hass(hass)
    result = await mock_old_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_old_config_entry.version == 2
    assert mock_old_config_entry.unique_id == CONF[CONF_ACCOUNT_ID]
    assert mock_old_config_entry.data == CONF


async def test_form_reauth_migrate_multi_account(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    mock_flick_client_multiple: AsyncMock,
) -> None:
    """Test the form when multiple accounts are available."""
    mock_old_config_entry.add_to_hass(hass)
    result = await mock_old_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNT_ID: CONF[CONF_ACCOUNT_ID]},
    )

    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert mock_old_config_entry.version == 2
    assert mock_old_config_entry.unique_id == CONF[CONF_ACCOUNT_ID]
    assert mock_old_config_entry.data == CONF


async def test_form_duplicate_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test uniqueness for account_id."""
    await setup_integration(hass, mock_config_entry)

    result = await _flow_submit(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=AuthException,
    ):
        result = await _flow_submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=TimeoutError,
    ):
        result = await _flow_submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_generic_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=Exception,
    ):
        result = await _flow_submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_select_account_cannot_connect(
    hass: HomeAssistant, mock_flick_client_multiple: AsyncMock
) -> None:
    """Test we handle connection errors for select account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch.object(
        mock_flick_client_multiple,
        "getPricing",
        side_effect=APIException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: CONF[CONF_USERNAME],
                CONF_PASSWORD: CONF[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "select_account"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ACCOUNT_ID: CONF[CONF_ACCOUNT_ID]},
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["step_id"] == "select_account"
        assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_select_account_invalid_auth(
    hass: HomeAssistant, mock_flick_client_multiple: AsyncMock
) -> None:
    """Test we handle auth errors for select account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_account"

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            side_effect=AuthException,
        ),
        patch.object(
            mock_flick_client_multiple,
            "getPricing",
            side_effect=AuthException,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ACCOUNT_ID: CONF[CONF_ACCOUNT_ID]},
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "no_permissions"


async def test_form_select_account_failed_to_connect(
    hass: HomeAssistant, mock_flick_client_multiple: AsyncMock
) -> None:
    """Test we handle connection errors for select account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_account"

    with (
        patch.object(
            mock_flick_client_multiple,
            "getCustomerAccounts",
            side_effect=APIException,
        ),
        patch.object(
            mock_flick_client_multiple,
            "getPricing",
            side_effect=APIException,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ACCOUNT_ID: CONF[CONF_ACCOUNT_ID]},
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "cannot_connect"}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_ACCOUNT_ID: ACCOUNT_ID_2},
    )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == ACCOUNT_NAME_2
    assert result4["data"] == {
        **CONF,
        CONF_SUPPLY_NODE_REF: SUPPLY_NODE_REF_2,
        CONF_ACCOUNT_ID: ACCOUNT_ID_2,
    }
    assert result4["result"].unique_id == ACCOUNT_ID_2


async def test_form_select_account_no_accounts(
    hass: HomeAssistant, mock_flick_client: AsyncMock
) -> None:
    """Test we handle connection errors for select account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch.object(
        mock_flick_client,
        "getCustomerAccounts",
        return_value=[
            {
                "id": "1234",
                "status": "closed",
                "address": "123 Fake St",
                "main_consumer": {"supply_node_ref": "123"},
            },
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: CONF[CONF_USERNAME],
                CONF_PASSWORD: CONF[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "no_accounts"
