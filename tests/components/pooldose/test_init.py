"""Test the Pooldose integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose import PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "pooldose"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="PoolDose Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="PDPR1H1HAW100_FW539187",
    )


@pytest.fixture
def mock_client():
    """Return a mocked PoolDose client."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    client.device_info = {
        "SERIAL_NUMBER": "PDPR1H1HAW100_FW539187",
        "MODEL": "PoolDose Pro",
        "FW_VERSION": "1.2.3",
        "SW_VERSION": "2.0.1",
        "API_VERSION": "v1.5/",
        "FW_CODE": "ABC123",
        "MAC": "AA:BB:CC:DD:EE:FF",
        "IP": "192.168.1.100",
    }
    return client


@pytest.fixture
def mock_coordinator():
    """Return a mocked coordinator."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ) as mock_forward,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is True
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Verify client was created with correct host
        assert mock_client.connect.called

        # Verify coordinator was created and first refresh was called
        assert mock_coordinator.async_config_entry_first_refresh.called

        # Verify platforms were forwarded
        mock_forward.assert_called_once_with(mock_config_entry, [Platform.SENSOR])

        # Verify runtime data was stored correctly
        runtime_data = mock_config_entry.runtime_data
        assert runtime_data.client == mock_client
        assert runtime_data.coordinator == mock_coordinator
        assert runtime_data.device_properties == mock_client.device_info


async def test_async_setup_entry_client_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when client connection fails."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
        mock_client_class.return_value = mock_client

        # Test setup result - ConfigEntryNotReady führt zu False return
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is False  # Setup failed
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY  # Status gesetzt


async def test_async_setup_entry_client_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when client has no data."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=RequestStatus.NO_DATA)
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_first_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test setup failure when coordinator first refresh fails."""
    mock_config_entry.add_to_hass(hass)
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=Exception("Failed to fetch data")
    )

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        # The exception from coordinator first refresh causes setup to fail
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_with_empty_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test setup with empty device info."""
    mock_config_entry.add_to_hass(hass)
    mock_client.device_info = {}

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is True
        # Verify empty device info is stored
        assert mock_config_entry.runtime_data.device_properties == {}


async def test_async_setup_entry_with_none_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test setup with None device info."""
    mock_config_entry.add_to_hass(hass)
    mock_client.device_info = None

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is True
        # Verify None device info is stored
        assert mock_config_entry.runtime_data.device_properties is None


async def test_async_unload_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test successful unloading of config entry."""
    # First set up the entry
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Now test unloading
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

        assert result is True
        mock_unload.assert_called_once_with(mock_config_entry, [Platform.SENSOR])


async def test_async_unload_entry_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test failed unloading of config entry."""
    # First set up the entry
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Now test failed unloading
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ) as mock_unload:
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

        assert result is False
        mock_unload.assert_called_once_with(mock_config_entry, [Platform.SENSOR])


@pytest.mark.parametrize(
    "status",
    [
        RequestStatus.HOST_UNREACHABLE,
        RequestStatus.PARAMS_FETCH_FAILED,
        RequestStatus.API_VERSION_UNSUPPORTED,
        RequestStatus.NO_DATA,
        RequestStatus.UNKNOWN_ERROR,
    ],
)
async def test_async_setup_entry_various_client_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status,
) -> None:
    """Test setup failure with various client error statuses."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=status)
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_pooldose_runtime_data_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
    mock_coordinator,
) -> None:
    """Test that PooldoseRuntimeData is properly structured."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # Test runtime data structure
        runtime_data = mock_config_entry.runtime_data

        # Verify all required fields are present
        assert hasattr(runtime_data, "client")
        assert hasattr(runtime_data, "coordinator")
        assert hasattr(runtime_data, "device_properties")

        # Verify field types and values
        assert runtime_data.client is mock_client
        assert runtime_data.coordinator is mock_coordinator
        assert runtime_data.device_properties == mock_client.device_info


async def test_config_entry_host_extraction(
    hass: HomeAssistant,
    mock_client,
    mock_coordinator,
) -> None:
    """Test that host is correctly extracted from config entry data."""
    test_host = "10.0.0.50"
    config_entry = MockConfigEntry(
        title="Test Device",
        domain=DOMAIN,
        data={CONF_HOST: test_host},
        unique_id="test_device_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class,
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator",
            return_value=mock_coordinator,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        mock_client_class.return_value = mock_client

        await hass.config_entries.async_setup(config_entry.entry_id)

        # Verify client was created with correct host
        mock_client_class.assert_called_once_with(test_host)


async def test_coordinator_creation_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
) -> None:
    """Test that coordinator is created with correct parameters."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseCoordinator"
        ) as mock_coordinator_class,
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # Verify coordinator was created with correct parameters
        mock_coordinator_class.assert_called_once_with(
            hass, mock_client, mock_config_entry
        )


def test_platforms_configuration() -> None:
    """Test that PLATFORMS is correctly configured."""
    assert PLATFORMS == [Platform.SENSOR]
    assert len(PLATFORMS) == 1
    assert Platform.SENSOR in PLATFORMS
