"""Test the OVO Energy config flow."""

from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.ovo_energy.const import CONF_ACCOUNT, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_REAUTH_INPUT = {CONF_PASSWORD: "something1"}
FIXTURE_USER_INPUT = {
    CONF_USERNAME: "example@example.com",
    CONF_PASSWORD: "something",
    CONF_ACCOUNT: "123456",
}

UNIQUE_ID = "example@example.com"


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
            return_value=False,
        ),
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.bootstrap_accounts",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.bootstrap_accounts",
        ),
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.username",
            "some_name",
        ),
        patch(
            "homeassistant.components.ovo_energy.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result2["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result2["data"][CONF_ACCOUNT] == FIXTURE_USER_INPUT[CONF_ACCOUNT]


async def test_reauth_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on authorization error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
    )
    mock_config.add_to_hass(hass)
    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        return_value=False,
    ):
        result = await mock_config.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_REAUTH_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth"
        assert result2["errors"] == {"base": "authorization_error"}


async def test_reauth_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
    )
    mock_config.add_to_hass(hass)
    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        side_effect=aiohttp.ClientError,
    ):
        result = await mock_config.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_REAUTH_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth"
        assert result2["errors"] == {"base": "connection_error"}


@pytest.mark.parametrize(  # Remove when translations fixed
    "ignore_translations",
    ["component.ovo_energy.config.abort.reauth_successful"],
)
async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth works."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data=FIXTURE_USER_INPUT
    )
    mock_config.add_to_hass(hass)
    with patch(
        "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
        return_value=False,
    ):
        result = await mock_config.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "authorization_error"}

    with (
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.ovo_energy.config_flow.OVOEnergy.username",
            return_value=FIXTURE_USER_INPUT[CONF_USERNAME],
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_REAUTH_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
