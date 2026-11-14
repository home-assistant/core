"""Tests for the Sony Projector config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sony_projector.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_projector")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test setting up a projector from the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST}


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionRefusedError, id="refused"),
        pytest.param(TimeoutError, id="read_timeout"),
        pytest.param(Exception("Timeout while connecting"), id="bare_exception"),
    ],
)
async def test_user_flow_cannot_connect_recovers(
    hass: HomeAssistant, mock_projector: MagicMock, error: Exception
) -> None:
    """Test a failed connection shows an error and the flow can recover."""
    mock_projector.get_power.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_projector.get_power.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_projector")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a projector can only be set up once from the UI."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_projector")
async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test importing a YAML platform aborts for a configured projector."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: TEST_HOST, CONF_NAME: "Cinema"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_projector")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing a YAML platform uses its name as the title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: TEST_HOST, CONF_NAME: "Cinema"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cinema"
    assert result["data"] == {CONF_HOST: TEST_HOST}


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_projector: MagicMock
) -> None:
    """Test importing a YAML platform aborts when the projector can't be reached."""
    mock_projector.get_power.side_effect = ConnectionRefusedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: TEST_HOST, CONF_NAME: "Cinema"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
