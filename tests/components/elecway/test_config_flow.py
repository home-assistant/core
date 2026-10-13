"""Test discovery, validation and duplicate prevention."""

from unittest.mock import AsyncMock

from aioelecway import ElecwayError
import pytest

from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import SERIAL

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_client")


@pytest.mark.usefixtures("mock_discover")
async def test_user(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Select a discovered device and confirm it without entering an IP address."""
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: SERIAL}
    )
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["data"][CONF_PORT] == 8080
    mock_client.connect.assert_awaited_once()
    mock_client.disconnect.assert_awaited_once()


async def test_zeroconf(hass: HomeAssistant, discovery: ZeroconfServiceInfo) -> None:
    """Zeroconf requires confirmation before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


@pytest.mark.usefixtures("mock_discover")
async def test_user_ignored_device(hass: HomeAssistant) -> None:
    """Manual setup replaces the ignored entry for the selected device."""
    ignored_entry = MockConfigEntry(
        domain="elecway", unique_id=SERIAL, source=SOURCE_IGNORE
    )
    ignored_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: SERIAL}
    )
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["result"].source == SOURCE_USER
    assert hass.config_entries.async_get_entry(ignored_entry.entry_id) is None
    assert hass.config_entries.async_entries("elecway") == [result["result"]]


async def test_zeroconf_ignored_device(
    hass: HomeAssistant, discovery: ZeroconfServiceInfo, mock_client: AsyncMock
) -> None:
    """Automatic rediscovery must still respect an ignored device."""
    ignored_entry = MockConfigEntry(
        domain="elecway", unique_id=SERIAL, source=SOURCE_IGNORE
    )
    ignored_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries("elecway") == [ignored_entry]
    mock_client.connect.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ElecwayError("Offline"), "cannot_connect", id="offline"),
        pytest.param(RuntimeError("Unexpected"), "unknown", id="unexpected"),
    ],
)
async def test_validation_failure(
    hass: HomeAssistant,
    discovery: ZeroconfServiceInfo,
    mock_client: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """Failed validation closes the probe and allows a retry."""
    mock_client.connect.side_effect = error
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": expected}
    mock_client.disconnect.assert_awaited_once()
    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


async def test_address_update(
    hass: HomeAssistant,
    discovery: ZeroconfServiceInfo,
    config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """An existing serial updates its network endpoint instead of being duplicated."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_HOST: "192.0.2.20", CONF_PORT: 80}
    )
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == discovery.host
    assert config_entry.data[CONF_PORT] == 8080
    mock_client.connect.assert_not_awaited()


async def test_no_devices(hass: HomeAssistant, mock_discover: AsyncMock) -> None:
    """No discovery produces actionable guidance."""
    mock_discover.return_value = {}
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_USER}
    )
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_discover")
async def test_all_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Configured devices are removed from the selection list."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_USER}
    )
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Printer._http._tcp.local.", id="unrelated"),
        pytest.param("EwayEnergyStorage-._http._tcp.local.", id="empty-serial"),
    ],
)
async def test_unsupported_discovery(
    hass: HomeAssistant, discovery: ZeroconfServiceInfo, name: str
) -> None:
    """The common HTTP service type is not enough to identify storage."""
    discovery.name = name
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["reason"] == "not_supported"


async def test_missing_port(
    hass: HomeAssistant, discovery: ZeroconfServiceInfo
) -> None:
    """Do not invent a port when discovery lacks one."""
    discovery.port = None
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["reason"] == "not_supported"


async def test_already_in_progress(
    hass: HomeAssistant, discovery: ZeroconfServiceInfo
) -> None:
    """Repeated announcements do not create competing flows."""
    await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    result = await hass.config_entries.flow.async_init(
        "elecway", context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["reason"] == "already_in_progress"
