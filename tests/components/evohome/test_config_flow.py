"""The tests for the evohome config flow."""

from typing import Any
from unittest.mock import PropertyMock, patch

import evohomeasync2 as ec2
from evohomeasync2.auth import AbstractTokenManager
import pytest

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.typing import ConfigType

from .conftest import mock_config_entry, mock_evohome_api, mock_post_request
from .const import USER_ID, USERNAME

NEW_PASSWORD = "new_password"
NEW_USERNAME = "new_user@gmail.com"

FLOW_ERROR_TESTS = [
    pytest.param(
        ec2.BadUserCredentialsError("Bad credentials"),
        "invalid_auth",
        id="invalid_auth",
    ),
    pytest.param(
        ec2.ApiConnectionFailedError("Connection failed"),
        "cannot_connect",
        id="cannot_connect",
    ),
    pytest.param(
        ec2.ApiRateLimitExceededError("Rate limit exceeded"),
        "cannot_connect",
        id="rate_limited",
    ),
    pytest.param(
        ec2.BadApiResponseError("Invalid response"),
        "cannot_connect",
        id="response_invalid",
    ),
    pytest.param(ValueError("Unexpected"), "unknown", id="unknown"),
]


async def test_user_flow(hass: HomeAssistant, config: ConfigType) -> None:
    """Test the user step creates an entry, which sets up without logging in again."""

    token_requests: list[str] = []
    post_request = mock_post_request("default")

    async def counted_post_request(
        self: AbstractTokenManager, url: str, /, **kwargs: Any
    ) -> Any:
        if "Token" in url:
            token_requests.append(url)
        return await post_request(self, url, **kwargs)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        mock_evohome_api("default"),
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            counted_post_request,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == config
    assert result["result"].unique_id == USER_ID
    assert result["result"].state is ConfigEntryState.LOADED

    assert len(token_requests) == 1  # by the flow, as the setup used its tokens


@pytest.mark.parametrize(("exception", "error"), FLOW_ERROR_TESTS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception,
    error: str,
) -> None:
    """Test the user step shows an error by its reason, and can then recover."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch.object(ec2.EvohomeClient, "setup", side_effect=exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_systems(hass: HomeAssistant, config: ConfigType) -> None:
    """Test the user step shows an error if no location has a TCS."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        mock_evohome_api("default"),
        patch.object(ec2.Location, "tcs", new_callable=PropertyMock, return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_systems"}

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_single_instance(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Test a second account can't be set up."""

    mock_config_entry(config).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_flow(hass: HomeAssistant, config: ConfigType) -> None:
    """Test a reauth updates the password, and reloads the entry."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == USERNAME

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_USERNAME: USERNAME, CONF_PASSWORD: NEW_PASSWORD}
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("exception", "error"), FLOW_ERROR_TESTS)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception,
    error: str,
) -> None:
    """Test a reauth shows an error by its reason, and can then recover."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch.object(ec2.EvohomeClient, "setup", side_effect=exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Test a reauth aborts if the credentials are of a different account."""

    entry = mock_config_entry(config, install="h157546")  # has another user id
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == config


async def test_reconfigure_flow(hass: HomeAssistant, config: ConfigType) -> None:
    """Test a reconfigure updates the credentials and title, and reloads the entry."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_config = {CONF_USERNAME: NEW_USERNAME, CONF_PASSWORD: NEW_PASSWORD}

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_config
    assert entry.title == NEW_USERNAME
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("exception", "error"), FLOW_ERROR_TESTS)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    config: ConfigType,
    exception: Exception,
    error: str,
) -> None:
    """Test a reconfigure shows an error by its reason, and can then recover."""

    entry = mock_config_entry(config)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch.object(ec2.EvohomeClient, "setup", side_effect=exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_wrong_account(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Test a reconfigure aborts if the credentials are of a different account."""

    entry = mock_config_entry(config, install="h157546")  # has another user id
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with mock_evohome_api("default"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: NEW_USERNAME, CONF_PASSWORD: NEW_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == config
