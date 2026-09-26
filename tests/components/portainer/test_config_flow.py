"""Test the Portainer config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.portainer import Endpoint, PortainerSystemStatus
import pytest

from homeassistant.components.portainer.const import (
    CONF_ENDPOINT_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENVIRONMENT,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry, ConfigSubentryData
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import MOCK_TEST_CONFIG, TEST_INSTANCE_ID

from tests.common import MockConfigEntry, async_load_json_array_fixture

MOCK_USER_SETUP = {
    CONF_URL: "https://127.0.0.1:9000/",
    CONF_API_TOKEN: "test_api_token",
    CONF_VERIFY_SSL: True,
}

USER_INPUT_RECONFIGURE = {
    CONF_URL: "https://new_domain:9000/",
    CONF_API_TOKEN: "new_api_key",
    CONF_VERIFY_SSL: True,
}


async def test_form(
    hass: HomeAssistant,
    mock_portainer_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:9000/"
    assert result["data"] == MOCK_TEST_CONFIG


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            PortainerAuthenticationError,
            "invalid_auth",
        ),
        (
            PortainerConnectionError,
            "cannot_connect",
        ),
        (
            PortainerTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions."""
    mock_portainer_client.portainer_system_status.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_portainer_client.portainer_system_status.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:9000/"
    assert result["data"] == MOCK_TEST_CONFIG


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow_reauth(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full flow of the config flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # There is no user input
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new_api_key"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new_api_key"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            PortainerAuthenticationError,
            "invalid_auth",
        ),
        (
            PortainerConnectionError,
            "cannot_connect",
        ),
        (
            PortainerTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions in the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    mock_portainer_client.portainer_system_status.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new_api_key"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    # Now test that we can recover from the error
    mock_portainer_client.portainer_system_status.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new_api_key"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new_api_key"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_flow_reconfigure(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full flow of the config flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new_api_key"
    assert mock_config_entry.data[CONF_URL] == "https://new_domain:9000/"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is True
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_flow_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts on different Portainer instance."""
    mock_config_entry.add_to_hass(hass)
    mock_portainer_client.portainer_system_status.return_value = PortainerSystemStatus(
        instance_id="different-instance-id", version="2.0.0"
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_API_TOKEN] == "test_api_token"
    assert mock_config_entry.data[CONF_URL] == "https://127.0.0.1:9000/"
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            PortainerAuthenticationError,
            "invalid_auth",
        ),
        (
            PortainerConnectionError,
            "cannot_connect",
        ),
        (
            PortainerTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_full_flow_reconfigure_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test the full flow of the config flow, this time with exceptions."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_portainer_client.portainer_system_status.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_portainer_client.portainer_system_status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new_api_key"
    assert mock_config_entry.data[CONF_URL] == "https://new_domain:9000/"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is True
    assert len(mock_setup_entry.mock_calls) == 1


async def test_environment_subentry_flow(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test creating an environment subentry for the remaining endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Portainer test",
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        version=5,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
                title="my-environment",
                unique_id="1",
            ),
        ],
    )
    await setup_integration(hass, entry)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENVIRONMENT),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ENDPOINT_ID: "42"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "my-edge-offline"
    assert result["unique_id"] == "42"
    assert len(entry.subentries) == 2


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (PortainerConnectionError("cannot connect"), "cannot_connect"),
        (PortainerTimeoutError("timeout"), "timeout_connect"),
        (PortainerAuthenticationError("invalid auth"), "invalid_auth"),
    ],
)
async def test_environment_subentry_flow_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test the environment subentry flow aborts on connection errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Portainer test",
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        version=5,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
                title="my-environment",
                unique_id="1",
            ),
        ],
    )
    await setup_integration(hass, entry)

    mock_portainer_client.get_endpoints.side_effect = exception
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENVIRONMENT),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_environment_subentry_flow_all_configured(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the environment subentry flow aborts when nothing is left to add."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ENVIRONMENT),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_new_environments"


async def test_environment_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the environment subentry flow aborts when the entry isn't loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ENVIRONMENT),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_loaded"


async def test_environment_subentry_flow_race_condition(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test the environment subentry flow aborts if configured mid-flow."""
    endpoints = await async_load_json_array_fixture(hass, "endpoints.json", DOMAIN)
    third_endpoint = {**endpoints[0], "Id": 99, "Name": "third-environment"}
    mock_portainer_client.get_endpoints.return_value = [
        Endpoint.from_dict(endpoint) for endpoint in (*endpoints, third_endpoint)
    ]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Portainer test",
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        version=5,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
                title="my-environment",
                unique_id="1",
            ),
        ],
    )
    await setup_integration(hass, entry)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENVIRONMENT),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={},
            subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
            title="my-edge-offline",
            unique_id="42",
        ),
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ENDPOINT_ID: "42"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_new_environments"
