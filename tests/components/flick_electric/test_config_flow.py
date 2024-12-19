"""Test the Flick Electric config flow."""

from unittest.mock import patch

from pyflick.authentication import AuthException
from pyflick.types import FlickPrice

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

from tests.common import MockConfigEntry

CONF = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_ACCOUNT_ID: "1234",
    CONF_SUPPLY_NODE_REF: "123",
}


def _mock_flick_price():
    return FlickPrice(
        {
            "cost": 0.25,
            "start_at": "2024-01-01T00:00:00Z",
            "end_at": "2024-01-01T00:00:00Z",
            "type": "flat",
            "components": [],
        }
    )


async def _flow_submit(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form with only one, with no account picker."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                }
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
        patch(
            "homeassistant.components.flick_electric.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "123 Fake St"
    assert result2["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multi_account(hass: HomeAssistant) -> None:
    """Test the form when multiple accounts are available."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                },
                {
                    "id": "5678",
                    "status": "active",
                    "address": "456 Fake St",
                    "main_consumer": {"supply_node_ref": "456"},
                },
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
        patch(
            "homeassistant.components.flick_electric.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "select_account"
        assert len(mock_setup_entry.mock_calls) == 0

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"account_id": "5678"},
        )

        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "456 Fake St"
        assert result3["data"] == {
            **CONF,
            CONF_SUPPLY_NODE_REF: "456",
            CONF_ACCOUNT_ID: "5678",
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_token(hass: HomeAssistant) -> None:
    """Test reauth flow when username/password is wrong."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONF},
        title="123 Fake St",
        unique_id="1234",
        version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            side_effect=AuthException,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=entry.data,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
        assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                },
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_update_entry",
            return_value=True,
        ) as mock_update_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert len(mock_update_entry.mock_calls) > 0


# TODO: Test migration

# TODO: Test reauth


async def test_form_duplicate_account(hass: HomeAssistant) -> None:
    """Test uniqueness for account_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONF, CONF_ACCOUNT_ID: "1234", CONF_SUPPLY_NODE_REF: "123"},
        title="123 Fake St",
        unique_id="1234",
        version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                }
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.config_flow.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
    ):
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
