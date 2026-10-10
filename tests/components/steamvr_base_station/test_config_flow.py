"""Test the SteamVR Base Station config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from lighthouse_ble import LighthouseConnectionError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.steamvr_base_station.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import STATION_SERVICE_INFO, TEST_ADDRESS, TEST_NAME, make_service_info

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

FLOW = "homeassistant.components.steamvr_base_station.config_flow"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:07"


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent the integration from setting up after the flow."""
    with patch(
        "homeassistant.components.steamvr_base_station.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_discovered_service_info() -> Generator[AsyncMock]:
    """Return the stations currently in range for the user step."""
    with patch(
        f"{FLOW}.async_discovered_service_info",
        return_value=[
            STATION_SERVICE_INFO,
            make_service_info(name="Pixel 9", address=OTHER_ADDRESS),
        ],
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_ble_device() -> Generator[AsyncMock]:
    """Make the station connectable."""
    with patch(
        f"{FLOW}.async_ble_device_from_address",
        return_value=generate_ble_device(TEST_ADDRESS, TEST_NAME),
    ) as mock:
        yield mock


async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_read_device_info: AsyncMock
) -> None:
    """Test setting up a discovered station after a successful connection check."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    mock_read_device_info.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == TEST_ADDRESS
    mock_read_device_info.assert_awaited_once()


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery aborts for a station that is already set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_already_in_progress(hass: HomeAssistant) -> None:
    """Test a second discovery of the same station aborts."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Steam Controller", id="other_valve_device"),
        pytest.param("LHB-00000000", id="boot_placeholder"),
    ],
)
async def test_bluetooth_discovery_not_supported(
    hass: HomeAssistant, name: str
) -> None:
    """Test discovery aborts for devices that are not V2 base stations."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=make_service_info(name=name),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            LighthouseConnectionError("no slot"), "cannot_connect", id="connection"
        ),
        pytest.param(RuntimeError("boom"), "unknown", id="unexpected"),
    ],
)
async def test_bluetooth_confirm_errors(
    hass: HomeAssistant,
    mock_read_device_info: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """Test a failed connection check shows an error and can be retried."""
    mock_read_device_info.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_read_device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_confirm_device_gone(
    hass: HomeAssistant, mock_ble_device: AsyncMock, mock_read_device_info: AsyncMock
) -> None:
    """Test the check fails without connecting when the station is out of range."""
    mock_ble_device.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=STATION_SERVICE_INFO
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    mock_read_device_info.assert_not_awaited()


@pytest.mark.usefixtures("mock_discovered_service_info")
async def test_user_step(hass: HomeAssistant, mock_read_device_info: AsyncMock) -> None:
    """Test picking a station that is in range, recovering from a failed check."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        TEST_ADDRESS: f"{TEST_NAME} ({TEST_ADDRESS})"
    }

    mock_read_device_info.side_effect = LighthouseConnectionError("no slot")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_read_device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TEST_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == TEST_ADDRESS


@pytest.mark.parametrize(
    "discovered",
    [
        pytest.param([], id="nothing_discovered"),
        pytest.param([STATION_SERVICE_INFO], id="already_set_up"),
    ],
)
async def test_user_step_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovered_service_info: AsyncMock,
    discovered: list[BluetoothServiceInfoBleak],
) -> None:
    """Test the user step aborts when no unconfigured station is in range."""
    mock_config_entry.add_to_hass(hass)
    mock_discovered_service_info.return_value = discovered
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
