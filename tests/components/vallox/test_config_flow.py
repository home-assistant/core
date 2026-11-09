"""Test the Vallox integration config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from vallox_websocket_api import ValloxApiException, ValloxWebsocketException

from homeassistant.components.vallox.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_HOST, TEST_NAME

OTHER_HOST = "192.168.100.60"
INVALID_HOST = "test.host.com"


@pytest.mark.usefixtures("mock_vallox_client")
async def test_form_create_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that an entry is created with valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_vallox_client", "mock_setup_entry")
async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test that an invalid host is rejected and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: INVALID_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}

    # Verify recovery without starting a new flow (rule config-flow-test-coverage).
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(ValloxApiException, "cannot_connect", id="api_error"),
        pytest.param(ValloxWebsocketException, "cannot_connect", id="websocket_error"),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test that connection errors are handled and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_vallox_client.fetch_metric_data.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: error}

    # Verify recovery without starting a new flow (rule config-flow-test-coverage).
    mock_vallox_client.fetch_metric_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME}


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a host that is already configured is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_vallox_client", "mock_setup_entry")
@pytest.mark.parametrize(
    "host",
    [
        pytest.param(OTHER_HOST, id="new_host"),
        # Resubmitting the current host is expected to succeed as well.
        pytest.param(TEST_HOST, id="unchanged_host"),
    ],
)
async def test_reconfigure_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, host: str
) -> None:
    """Test that the host can be reconfigured."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == host


@pytest.mark.usefixtures("mock_vallox_client", "mock_setup_entry")
async def test_reconfigure_host_to_same_host_as_another_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that changing the host to the host of another entry fails."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: OTHER_HOST, CONF_NAME: "Vallox 2"},
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST


@pytest.mark.usefixtures("mock_vallox_client", "mock_setup_entry")
async def test_reconfigure_invalid_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an invalid host is rejected and the reconfigure flow recovers."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: INVALID_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST

    # Verify recovery without starting a new flow (rule config-flow-test-coverage).
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == OTHER_HOST


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(ValloxApiException, "cannot_connect", id="api_error"),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vallox_client: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test that connection errors are handled and the reconfigure flow recovers."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_vallox_client.fetch_metric_data.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: error}
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST

    # Verify recovery without starting a new flow (rule config-flow-test-coverage).
    mock_vallox_client.fetch_metric_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == OTHER_HOST
