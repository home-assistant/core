"""Tests for button entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.unraid.button import (
    ArrayStartButton,
    ArrayStopButton,
    DiskSpinDownButton,
    DiskSpinUpButton,
    ParityCheckPauseButton,
    ParityCheckResumeButton,
    ParityCheckStartButton,
    ParityCheckStartCorrectionButton,
    ParityCheckStopButton,
    async_setup_entry,
)
from homeassistant.components.unraid.coordinator import UnraidStorageData
from homeassistant.components.unraid.models import ArrayDisk
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.start_array = AsyncMock(return_value={"array": {"state": "STARTED"}})
    client.stop_array = AsyncMock(return_value={"array": {"state": "STOPPED"}})
    client.start_parity_check = AsyncMock(return_value={"parityCheck": {"start": True}})
    client.pause_parity_check = AsyncMock(return_value={"parityCheck": {"pause": True}})
    client.resume_parity_check = AsyncMock(
        return_value={"parityCheck": {"resume": True}}
    )
    client.cancel_parity_check = AsyncMock(
        return_value={"parityCheck": {"cancel": True}}
    )
    client.spin_up_disk = AsyncMock(
        return_value={"array": {"mountArrayDisk": {"isSpinning": True}}}
    )
    client.spin_down_disk = AsyncMock(
        return_value={"array": {"unmountArrayDisk": {"isSpinning": False}}}
    )
    return client


@pytest.fixture
def mock_storage_coordinator():
    """Create a mock storage coordinator."""
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_disk():
    """Create a mock disk."""
    return ArrayDisk(
        id="disk:1",
        idx=1,
        name="Disk 1",
        device="sda",
        type="DATA",
    )


class TestArrayStartButton:
    """Test ArrayStartButton."""

    def test_button_creation(self, mock_api_client):
        """Test array start button is created correctly."""
        button = ArrayStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Start Array"
        assert button.unique_id == "test-uuid_array_start"
        assert button.translation_key == "array_start"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing array start button calls API."""
        button = ArrayStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.start_array.assert_called_once()


class TestArrayStopButton:
    """Test ArrayStopButton."""

    def test_button_creation(self, mock_api_client):
        """Test array stop button is created correctly."""
        button = ArrayStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Stop Array"
        assert button.unique_id == "test-uuid_array_stop"
        assert button.translation_key == "array_stop"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing array stop button calls API."""
        button = ArrayStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.stop_array.assert_called_once()


class TestParityCheckStartButton:
    """Test ParityCheckStartButton."""

    def test_button_creation(self, mock_api_client):
        """Test parity check start button is created correctly."""
        button = ParityCheckStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Start Parity Check"
        assert button.unique_id == "test-uuid_parity_check_start"
        assert button.translation_key == "parity_check_start"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing parity check start button calls API with correct=False."""
        button = ParityCheckStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.start_parity_check.assert_called_once_with(correct=False)


class TestParityCheckStartCorrectionButton:
    """Test ParityCheckStartCorrectionButton."""

    def test_button_creation(self, mock_api_client):
        """Test parity check correction button is created correctly."""
        button = ParityCheckStartCorrectionButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Start Parity Check (Correcting)"
        assert button.unique_id == "test-uuid_parity_check_start_correct"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing correction button calls API with correct=True."""
        button = ParityCheckStartCorrectionButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.start_parity_check.assert_called_once_with(correct=True)


class TestParityCheckPauseButton:
    """Test ParityCheckPauseButton."""

    def test_button_creation(self, mock_api_client):
        """Test parity check pause button is created correctly."""
        button = ParityCheckPauseButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Pause Parity Check"
        assert button.translation_key == "parity_check_pause"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing pause button calls API."""
        button = ParityCheckPauseButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.pause_parity_check.assert_called_once()


class TestParityCheckResumeButton:
    """Test ParityCheckResumeButton."""

    def test_button_creation(self, mock_api_client):
        """Test parity check resume button is created correctly."""
        button = ParityCheckResumeButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Resume Parity Check"
        assert button.translation_key == "parity_check_resume"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing resume button calls API."""
        button = ParityCheckResumeButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.resume_parity_check.assert_called_once()


class TestParityCheckStopButton:
    """Test ParityCheckStopButton."""

    def test_button_creation(self, mock_api_client):
        """Test parity check stop button is created correctly."""
        button = ParityCheckStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        assert button.name == "Stop Parity Check"
        assert button.translation_key == "parity_check_stop"

    @pytest.mark.asyncio
    async def test_button_press(self, mock_api_client):
        """Test pressing stop button calls API."""
        button = ParityCheckStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        await button.async_press()
        mock_api_client.cancel_parity_check.assert_called_once()


class TestDiskSpinUpButton:
    """Test DiskSpinUpButton."""

    def test_button_creation(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test disk spin up button is created correctly."""
        button = DiskSpinUpButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        assert button.name == "Spin Up Disk 1"
        assert button.unique_id == "test-uuid_disk_spin_up_disk:1"
        assert button.translation_key == "disk_spin_up"

    @pytest.mark.asyncio
    async def test_button_press(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test pressing spin up button calls API and refreshes coordinator."""
        button = DiskSpinUpButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        await button.async_press()
        mock_api_client.spin_up_disk.assert_called_once_with("disk:1")
        mock_storage_coordinator.async_request_refresh.assert_called_once()


class TestDiskSpinDownButton:
    """Test DiskSpinDownButton."""

    def test_button_creation(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test disk spin down button is created correctly."""
        button = DiskSpinDownButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        assert button.name == "Spin Down Disk 1"
        assert button.unique_id == "test-uuid_disk_spin_down_disk:1"
        assert button.translation_key == "disk_spin_down"

    @pytest.mark.asyncio
    async def test_button_press(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test pressing spin down button calls API and refreshes coordinator."""
        button = DiskSpinDownButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        await button.async_press()
        mock_api_client.spin_down_disk.assert_called_once_with("disk:1")
        mock_storage_coordinator.async_request_refresh.assert_called_once()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestButtonErrorHandling:
    """Test button error handling."""

    @pytest.mark.asyncio
    async def test_array_start_button_error(self, mock_api_client):
        """Test array start button raises HomeAssistantError on failure."""

        mock_api_client.start_array = AsyncMock(side_effect=Exception("API Error"))
        button = ArrayStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to start array"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_array_stop_button_error(self, mock_api_client):
        """Test array stop button raises HomeAssistantError on failure."""

        mock_api_client.stop_array = AsyncMock(side_effect=Exception("API Error"))
        button = ArrayStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to stop array"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_parity_check_start_button_error(self, mock_api_client):
        """Test parity check start button raises HomeAssistantError on failure."""

        mock_api_client.start_parity_check = AsyncMock(
            side_effect=Exception("API Error")
        )
        button = ParityCheckStartButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to start parity check"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_parity_check_correction_button_error(self, mock_api_client):
        """Test parity check correction button raises HomeAssistantError."""

        mock_api_client.start_parity_check = AsyncMock(
            side_effect=Exception("API Error")
        )
        button = ParityCheckStartCorrectionButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(
            HomeAssistantError, match="Failed to start correcting parity check"
        ):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_parity_check_pause_button_error(self, mock_api_client):
        """Test parity check pause button raises HomeAssistantError on failure."""

        mock_api_client.pause_parity_check = AsyncMock(
            side_effect=Exception("API Error")
        )
        button = ParityCheckPauseButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to pause parity check"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_parity_check_resume_button_error(self, mock_api_client):
        """Test parity check resume button raises HomeAssistantError on failure."""

        mock_api_client.resume_parity_check = AsyncMock(
            side_effect=Exception("API Error")
        )
        button = ParityCheckResumeButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to resume parity check"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_parity_check_stop_button_error(self, mock_api_client):
        """Test parity check stop button raises HomeAssistantError on failure."""

        mock_api_client.cancel_parity_check = AsyncMock(
            side_effect=Exception("API Error")
        )
        button = ParityCheckStopButton(
            api_client=mock_api_client,
            server_uuid="test-uuid",
            server_name="Test Server",
        )
        with pytest.raises(HomeAssistantError, match="Failed to stop parity check"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_disk_spin_up_button_error(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test disk spin up button raises HomeAssistantError on failure."""

        mock_api_client.spin_up_disk = AsyncMock(side_effect=Exception("API Error"))
        button = DiskSpinUpButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        with pytest.raises(HomeAssistantError, match="Failed to spin up disk"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_disk_spin_down_button_error(
        self, mock_api_client, mock_storage_coordinator, mock_disk
    ):
        """Test disk spin down button raises HomeAssistantError on failure."""

        mock_api_client.spin_down_disk = AsyncMock(side_effect=Exception("API Error"))
        button = DiskSpinDownButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=mock_disk,
        )
        with pytest.raises(HomeAssistantError, match="Failed to spin down disk"):
            await button.async_press()


# =============================================================================
# async_setup_entry Tests
# =============================================================================


class TestButtonSetupEntry:
    """Test async_setup_entry for button platform."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_array_buttons(self, hass):
        """Test that setup creates array control buttons."""

        mock_api = MagicMock()
        mock_storage_coordinator = MagicMock()
        mock_storage_coordinator.data = None

        runtime_data = MagicMock()
        runtime_data.api_client = mock_api
        runtime_data.storage_coordinator = mock_storage_coordinator
        runtime_data.server_info = {
            "uuid": "test-uuid",
            "name": "Test Server",
            "manufacturer": "Test",
            "model": "Server",
        }

        mock_entry = MagicMock()
        mock_entry.runtime_data = runtime_data
        mock_entry.data = {"host": "192.168.1.100"}

        entities = []

        def capture_entities(ents) -> None:
            entities.extend(ents)

        await async_setup_entry(hass, mock_entry, capture_entities)

        # Should have array start, stop, parity check start, stop = 4 buttons
        assert len(entities) == 4
        entity_types = [type(e).__name__ for e in entities]
        assert "ArrayStartButton" in entity_types
        assert "ArrayStopButton" in entity_types
        assert "ParityCheckStartButton" in entity_types
        assert "ParityCheckStopButton" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_creates_disk_buttons(self, hass):
        """Test that setup creates disk spin buttons when storage data exists."""

        mock_api = MagicMock()

        # Create mock storage data with disks
        storage_data = UnraidStorageData(
            disks=[
                ArrayDisk(id="disk:1", idx=1, name="Disk 1"),
                ArrayDisk(id="disk:2", idx=2, name="Disk 2"),
            ],
            parities=[ArrayDisk(id="parity:1", idx=0, name="Parity")],
            caches=[ArrayDisk(id="cache:1", idx=0, name="Cache")],
            shares=[],
            array_state="STARTED",
            capacity=None,
            parity_status=None,
        )

        mock_storage_coordinator = MagicMock()
        mock_storage_coordinator.data = storage_data

        runtime_data = MagicMock()
        runtime_data.api_client = mock_api
        runtime_data.storage_coordinator = mock_storage_coordinator
        runtime_data.server_info = {"uuid": "test-uuid", "name": "Test Server"}

        mock_entry = MagicMock()
        mock_entry.runtime_data = runtime_data
        mock_entry.data = {"host": "192.168.1.100"}

        entities = []

        def capture_entities(ents) -> None:
            entities.extend(ents)

        await async_setup_entry(hass, mock_entry, capture_entities)

        # 4 base buttons + 4 disks * 2 spin buttons = 12 buttons
        assert len(entities) == 12

        # Verify disk buttons were created
        spin_up_buttons = [
            e for e in entities if type(e).__name__ == "DiskSpinUpButton"
        ]
        spin_down_buttons = [
            e for e in entities if type(e).__name__ == "DiskSpinDownButton"
        ]
        assert len(spin_up_buttons) == 4
        assert len(spin_down_buttons) == 4

    @pytest.mark.asyncio
    async def test_setup_entry_with_missing_server_uuid(self, hass):
        """Test setup with missing server UUID uses 'unknown'."""

        mock_api = MagicMock()
        mock_storage_coordinator = MagicMock()
        mock_storage_coordinator.data = None

        runtime_data = MagicMock()
        runtime_data.api_client = mock_api
        runtime_data.storage_coordinator = mock_storage_coordinator
        runtime_data.server_info = {}  # No uuid

        mock_entry = MagicMock()
        mock_entry.runtime_data = runtime_data
        mock_entry.data = {"host": "192.168.1.100"}

        entities = []

        def capture_entities(ents) -> None:
            entities.extend(ents)

        await async_setup_entry(hass, mock_entry, capture_entities)

        # Check that entities were created with "unknown" uuid
        assert len(entities) == 4
        assert entities[0].unique_id.startswith("unknown_")


class TestDiskButtonWithNoName:
    """Test disk buttons when disk has no name."""

    def test_disk_spin_up_uses_id_when_no_name(
        self, mock_api_client, mock_storage_coordinator
    ):
        """Test disk spin up uses disk ID when name is None."""
        disk = ArrayDisk(id="disk:5", idx=5, name=None)
        button = DiskSpinUpButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=disk,
        )
        # Should fall back to disk.id
        assert button.name == "Spin Up disk:5"

    def test_disk_spin_down_uses_id_when_no_name(
        self, mock_api_client, mock_storage_coordinator
    ):
        """Test disk spin down uses disk ID when name is None."""
        disk = ArrayDisk(id="disk:5", idx=5, name=None)
        button = DiskSpinDownButton(
            api_client=mock_api_client,
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="Test Server",
            disk=disk,
        )
        # Should fall back to disk.id
        assert button.name == "Spin Down disk:5"
