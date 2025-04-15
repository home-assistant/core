"""Tests for the Rain Bird config flow."""

from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.rainbird import DOMAIN
from homeassistant.components.rainbird.const import ATTR_DURATION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from .conftest import (
    CONFIG_ENTRY_DATA,
    HOST,
    MAC_ADDRESS_UNIQUE_ID,
    PASSWORD,
    SERIAL_NUMBER,
    SERIAL_RESPONSE,
    URL,
    WIFI_PARAMS_RESPONSE,
    ZERO_SERIAL_RESPONSE,
    mock_json_response,
    mock_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture(name="responses")
def mock_responses() -> list[AiohttpClientMockResponse]:
    """Set up fake serial number response when testing the connection."""
    return [mock_response(SERIAL_RESPONSE), mock_json_response(WIFI_PARAMS_RESPONSE)]


@pytest.fixture(autouse=True)
async def config_entry_data() -> dict[str, Any] | None:
    """Fixture to disable config entry setup for exercising config flow."""
    return None


@pytest.fixture(autouse=True)
async def mock_setup() -> AsyncGenerator[AsyncMock]:
    """Fixture for patching out integration setup."""

    with patch(
        "homeassistant.components.rainbird.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


async def complete_flow(hass: HomeAssistant, password: str = PASSWORD) -> FlowResult:
    """Start the config flow and enter the host and password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert not result.get("errors")
    assert "flow_id" in result

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD},
    )


@pytest.mark.parametrize(
    ("responses", "expected_config_entry", "expected_unique_id"),
    [
        (
            [
                mock_response(SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            CONFIG_ENTRY_DATA,
            MAC_ADDRESS_UNIQUE_ID,
        ),
        (
            [
                mock_response(ZERO_SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            {**CONFIG_ENTRY_DATA, "serial_number": 0},
            MAC_ADDRESS_UNIQUE_ID,
        ),
    ],
)
async def test_controller_flow(
    hass: HomeAssistant,
    mock_setup: Mock,
    expected_config_entry: dict[str, str],
    expected_unique_id: int | None,
) -> None:
    """Test the controller is setup correctly."""

    result = await complete_flow(hass)
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == HOST
    assert "result" in result
    assert dict(result["result"].data) == expected_config_entry
    assert result["result"].options == {ATTR_DURATION: 6}
    assert result["result"].unique_id == expected_unique_id

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "config_entry_unique_id",
        "config_entry_data",
        "config_flow_responses",
        "expected_config_entry",
    ),
    [
        (
            "other-serial-number",
            {**CONFIG_ENTRY_DATA, "host": "other-host"},
            [mock_response(SERIAL_RESPONSE), mock_json_response(WIFI_PARAMS_RESPONSE)],
            CONFIG_ENTRY_DATA,
        ),
        (
            "11:22:33:44:55:66",
            {
                **CONFIG_ENTRY_DATA,
                "host": "other-host",
            },
            [
                mock_response(SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            CONFIG_ENTRY_DATA,
        ),
        (
            None,
            {**CONFIG_ENTRY_DATA, "serial_number": 0, "host": "other-host"},
            [
                mock_response(ZERO_SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            {**CONFIG_ENTRY_DATA, "serial_number": 0},
        ),
    ],
    ids=["with-serial", "with-mac-address", "zero-serial"],
)
async def test_multiple_config_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    responses: list[AiohttpClientMockResponse],
    config_flow_responses: list[AiohttpClientMockResponse],
    expected_config_entry: dict[str, Any] | None,
) -> None:
    """Test setting up multiple config entries that refer to different devices."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    responses.clear()
    responses.extend(config_flow_responses)

    result = await complete_flow(hass)
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert dict(result.get("result").data) == expected_config_entry

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


@pytest.mark.parametrize(
    (
        "config_entry_unique_id",
        "config_entry_data",
        "config_flow_responses",
        "expected_config_entry_data",
    ),
    [
        # Config entry is a pure duplicate with the same mac address unique id
        (
            MAC_ADDRESS_UNIQUE_ID,
            CONFIG_ENTRY_DATA,
            [
                mock_response(SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            CONFIG_ENTRY_DATA,
        ),
        # Old unique id with serial, but same host
        (
            SERIAL_NUMBER,
            CONFIG_ENTRY_DATA,
            [mock_response(SERIAL_RESPONSE), mock_json_response(WIFI_PARAMS_RESPONSE)],
            CONFIG_ENTRY_DATA,
        ),
        # Old unique id with no serial, but same host
        (
            None,
            {**CONFIG_ENTRY_DATA, "serial_number": 0},
            [
                mock_response(ZERO_SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            {**CONFIG_ENTRY_DATA, "serial_number": 0},
        ),
        # Enters a different hostname that points to the same mac address
        (
            MAC_ADDRESS_UNIQUE_ID,
            {
                **CONFIG_ENTRY_DATA,
                "host": f"other-{HOST}",
            },
            [mock_response(SERIAL_RESPONSE), mock_json_response(WIFI_PARAMS_RESPONSE)],
            CONFIG_ENTRY_DATA,  # Updated the host
        ),
    ],
    ids=[
        "duplicate-mac-unique-id",
        "duplicate-host-legacy-serial-number",
        "duplicate-host-port-no-serial",
        "duplicate-duplicate-hostname",
    ],
)
async def test_duplicate_config_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    responses: list[AiohttpClientMockResponse],
    config_flow_responses: list[AiohttpClientMockResponse],
    expected_config_entry_data: dict[str, Any],
) -> None:
    """Test that a device can not be registered twice."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    responses.clear()
    responses.extend(config_flow_responses)

    result = await complete_flow(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert dict(config_entry.data) == expected_config_entry_data


async def test_controller_cannot_connect(
    hass: HomeAssistant,
    mock_setup: Mock,
    responses: list[AiohttpClientMockResponse],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an error talking to the controller."""

    # Controller response with a failure
    responses.clear()
    responses.append(
        AiohttpClientMockResponse("POST", URL, status=HTTPStatus.SERVICE_UNAVAILABLE)
    )

    result = await complete_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    assert not mock_setup.mock_calls


async def test_controller_invalid_auth(
    hass: HomeAssistant,
    mock_setup: Mock,
    responses: list[AiohttpClientMockResponse],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an invalid password."""

    responses.clear()
    responses.extend(
        [
            # Incorrect password response
            AiohttpClientMockResponse("POST", URL, status=HTTPStatus.FORBIDDEN),
            AiohttpClientMockResponse("POST", URL, status=HTTPStatus.FORBIDDEN),
            # Second attempt with the correct password
            mock_response(SERIAL_RESPONSE),
            mock_json_response(WIFI_PARAMS_RESPONSE),
        ]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert not result.get("errors")
    assert "flow_id" in result

    # Simulate authentication error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_PASSWORD: "wrong-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "invalid_auth"}

    assert not mock_setup.mock_calls

    # Correct the form and enter the password again and setup completes
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == HOST
    assert "result" in result
    assert dict(result["result"].data) == CONFIG_ENTRY_DATA
    assert result["result"].unique_id == MAC_ADDRESS_UNIQUE_ID

    assert len(mock_setup.mock_calls) == 1


async def test_controller_timeout(
    hass: HomeAssistant,
    mock_setup: Mock,
) -> None:
    """Test an error talking to the controller."""

    with patch(
        "homeassistant.components.rainbird.config_flow.asyncio.timeout",
        side_effect=TimeoutError,
    ):
        result = await complete_flow(hass)
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "user"
        assert result.get("errors") == {"base": "timeout_connect"}

    assert not mock_setup.mock_calls


@pytest.mark.parametrize(
    ("responses", "config_entry_data"),
    [
        (
            [
                # First attempt simulate the wrong password
                AiohttpClientMockResponse("POST", URL, status=HTTPStatus.FORBIDDEN),
                AiohttpClientMockResponse("POST", URL, status=HTTPStatus.FORBIDDEN),
                # Second attempt simulate the correct password
                mock_response(SERIAL_RESPONSE),
                mock_json_response(WIFI_PARAMS_RESPONSE),
            ],
            {
                **CONFIG_ENTRY_DATA,
                CONF_PASSWORD: "old-password",
            },
        ),
    ],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the controller is setup correctly."""
    assert config_entry.data.get(CONF_PASSWORD) == "old-password"
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result.get("step_id") == "reauth_confirm"
    assert not result.get("errors")

    # Simluate the wrong password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "incorrect_password"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("errors") == {"base": "invalid_auth"}

    # Enter the correct password and complete the flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: PASSWORD},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == MAC_ADDRESS_UNIQUE_ID
    assert entry.data.get(CONF_PASSWORD) == PASSWORD

    assert len(mock_setup.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant, mock_setup: Mock) -> None:
    """Test config flow options."""

    # Setup config flow
    result = await complete_flow(hass)
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == HOST
    assert "result" in result
    assert result["result"].data == CONFIG_ENTRY_DATA
    assert result["result"].options == {ATTR_DURATION: 6}

    # Assert single config entry is loaded
    config_entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    assert config_entry.state is ConfigEntryState.LOADED

    # Initiate the options flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Change the default duration
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={ATTR_DURATION: 5}
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        ATTR_DURATION: 5,
    }
