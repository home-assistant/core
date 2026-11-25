"""Test the ADS config flow."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pyads
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ads.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ADS_CONFIG
from .const import AMS_NET_ID, IP_ADDRESS, PORT

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture
def mock_validate_connection() -> None:
    """Run the real connection probe, against the mocked pyads Connection."""


CONNECT_ERRORS = [
    pytest.param(
        lambda mock: setattr(
            mock.return_value.read_state,
            "side_effect",
            pyads.ADSError(err_code=1861),
        ),
        "cannot_connect",
        id="timeout",
    ),
    pytest.param(
        lambda mock: setattr(mock.return_value.read_state, "return_value", None),
        "cannot_connect",
        id="port_closed",
    ),
    pytest.param(
        lambda mock: setattr(
            mock, "side_effect", ValueError("invalid literal for int() with base 10")
        ),
        "invalid_net_id",
        id="invalid_net_id",
    ),
    pytest.param(
        lambda mock: setattr(
            mock.return_value.open,
            "side_effect",
            RuntimeError("Failed to open port on AMS router."),
        ),
        "cannot_connect",
        id="router_down",
    ),
    pytest.param(
        lambda mock: setattr(mock.return_value.read_state, "side_effect", TypeError),
        "unknown",
        id="unknown",
    ),
]


async def test_user_flow(hass: HomeAssistant, mock_pyads_connection: MagicMock) -> None:
    """Test the user flow creates an entry once the device answers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ADS_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AMS_NET_ID
    assert result["data"] == ADS_CONFIG
    mock_pyads_connection.assert_called_once_with(AMS_NET_ID, PORT, IP_ADDRESS)
    client = mock_pyads_connection.return_value
    client.read_state.assert_called_once()
    # The probe does not keep the connection open.
    client.close.assert_called_once()


@pytest.mark.parametrize(("configure_mock", "error"), CONNECT_ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    configure_mock: Callable[[MagicMock], None],
    error: str,
) -> None:
    """Test the user flow shows an error and recovers once the device answers."""
    configure_mock(mock_pyads_connection)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ADS_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pyads_connection.side_effect = None
    client = mock_pyads_connection.return_value
    client.open.side_effect = None
    client.read_state.side_effect = None
    client.read_state.return_value = (5, 0)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ADS_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ADS_CONFIG


async def test_user_flow_unreachable(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_create_connection: MagicMock,
) -> None:
    """Test an unreachable device is reported at once, without pyads."""
    mock_create_connection.side_effect = TimeoutError("timed out")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ADS_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_pyads_connection.assert_not_called()

    mock_create_connection.side_effect = None
    mock_pyads_connection.return_value.read_state.return_value = (5, 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ADS_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_user_flow_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only a single connection can be configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing the connection from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=ADS_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AMS_NET_ID
    assert result["data"] == ADS_CONFIG


@pytest.mark.parametrize(
    "configure_mock",
    [
        pytest.param(param.values[0], id=param.id)
        for param in CONNECT_ERRORS
        if param.id != "invalid_net_id"
    ],
)
async def test_import_flow_offline(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    configure_mock: Callable[[MagicMock], None],
) -> None:
    """Test the import creates the entry without connecting to the device."""
    configure_mock(mock_pyads_connection)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=ADS_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ADS_CONFIG
    mock_pyads_connection.assert_not_called()


@pytest.mark.parametrize(
    "net_id", ["bad", "1.2.3.4.5", "1.2.3.4.5.256", "1.2.3.4.5.x", "1.2.3.4.5.6.7"]
)
async def test_import_flow_invalid_net_id(hass: HomeAssistant, net_id: str) -> None:
    """Test the import aborts on an AMS NetID that cannot be valid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**ADS_CONFIG, CONF_DEVICE: net_id},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_net_id"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the connection, prefilled with the current settings."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"].schema
    assert {
        key: key.description["suggested_value"] for key in schema if key.description
    } == ADS_CONFIG

    new_net_id = "192.168.1.20.1.1"
    new_config = {**ADS_CONFIG, CONF_DEVICE: new_net_id, CONF_PORT: 852}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_config
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new_config
    assert mock_config_entry.title == new_net_id


async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test a reconfiguration the device does not answer is retried, not stored."""
    mock_config_entry.add_to_hass(hass)
    mock_pyads_connection.return_value.read_state.side_effect = pyads.ADSError(
        err_code=1861
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ADS_CONFIG, CONF_PORT: 852}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data == ADS_CONFIG

    mock_pyads_connection.return_value.read_state.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ADS_CONFIG, CONF_PORT: 852}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**ADS_CONFIG, CONF_PORT: 852}


async def test_reconfigure_flow_clears_optional_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test a cleared IP address is dropped instead of stored as a blank."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ADS_CONFIG, CONF_IP_ADDRESS: ""}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_DEVICE: AMS_NET_ID, CONF_PORT: PORT}
    # A blank address would be used as is instead of derived from the NetID.
    mock_pyads_connection.assert_called_once_with(AMS_NET_ID, PORT, None)
