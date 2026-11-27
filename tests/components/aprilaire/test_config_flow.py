"""Tests for the Aprilaire config flow."""

from collections.abc import Generator
from unittest.mock import ANY, AsyncMock, patch

from pyaprilaire.client import AprilaireClient, NackError, ResponseTimeoutError
from pyaprilaire.const import FunctionalDomain, NackStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def client() -> Generator[AsyncMock]:
    """Return a mock client that reports a MAC address."""
    client = AsyncMock(AprilaireClient)
    client.read_mac_address_and_wait.return_value = {"mac_address": "1:2:3:4:5:6"}
    with patch(
        "homeassistant.components.aprilaire.config_flow.AprilaireClient",
        return_value=client,
    ) as client_class:
        client.client_class = client_class
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.aprilaire.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_data(client: AsyncMock, hass: HomeAssistant) -> None:
    """Test the config flow with valid data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "localhost", "port": 7000}
    )
    await hass.async_block_till_done()

    client.client_class.assert_called_once_with("localhost", 7000, ANY)
    client.start_listen_once.assert_awaited_once()
    client.read_mac_address_and_wait.assert_awaited_once_with(30)
    client.stop_listen.assert_called_once()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AprilAire"
    assert result["data"] == {"host": "localhost", "port": 7000}
    assert result["result"].unique_id == "1:2:3:4:5:6"


@pytest.mark.parametrize(
    ("connect_side_effect", "read_side_effect", "read_return_value"),
    [
        pytest.param(OSError(), None, None, id="cannot_connect"),
        pytest.param(
            None,
            ResponseTimeoutError(FunctionalDomain.IDENTIFICATION, 2, 30),
            None,
            id="timeout",
        ),
        pytest.param(
            None,
            NackError(NackStatus.GENERIC_ERROR, NackStatus.GENERIC_ERROR.value),
            None,
            id="nack",
        ),
        pytest.param(None, None, {}, id="missing"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_invalid_data(
    client: AsyncMock,
    hass: HomeAssistant,
    connect_side_effect: Exception | None,
    read_side_effect: Exception | None,
    read_return_value: dict[str, str] | None,
) -> None:
    """Test that the flow shows an error with invalid data and can recover."""
    client.start_listen_once.side_effect = connect_side_effect
    client.read_mac_address_and_wait.side_effect = read_side_effect
    client.read_mac_address_and_wait.return_value = read_return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "localhost", "port": 8000}
    )

    client.stop_listen.assert_called_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_failed"}
    suggested_values = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
    }
    assert suggested_values == {"host": "localhost", "port": 8000}

    client.start_listen_once.side_effect = None
    client.read_mac_address_and_wait.side_effect = None
    client.read_mac_address_and_wait.return_value = {"mac_address": "1:2:3:4:5:6"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "localhost", "port": 8000}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1:2:3:4:5:6"
    assert result["data"] == {"host": "localhost", "port": 8000}


@pytest.mark.usefixtures("client")
async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test the config flow aborts when the device is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1:2:3:4:5:6",
        data={"host": "localhost", "port": 7000},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "localhost", "port": 7000}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry that is added to Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1:2:3:4:5:6",
        data={"host": "localhost", "port": 7000},
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_reconfigure(
    client: AsyncMock,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring the host and port."""
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.10", "port": 8000}
    )
    await hass.async_block_till_done()

    client.client_class.assert_called_once_with("192.168.1.10", 8000, ANY)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {"host": "192.168.1.10", "port": 8000}
    mock_setup_entry.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_connection_failed(
    client: AsyncMock, hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring shows an error when the connection fails and can recover."""
    client.start_listen_once.side_effect = OSError()
    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.10", "port": 8000}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "connection_failed"}

    client.start_listen_once.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.10", "port": 8000}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {"host": "192.168.1.10", "port": 8000}


async def test_reconfigure_wrong_device(
    client: AsyncMock, hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring aborts when a different thermostat answers."""
    client.read_mac_address_and_wait.return_value = {"mac_address": "6:5:4:3:2:1"}
    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.10", "port": 8000}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data == {"host": "localhost", "port": 7000}
