"""Tests for Unraid switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.unraid import UnraidRuntimeData
from homeassistant.components.unraid.coordinator import UnraidSystemCoordinator
from homeassistant.components.unraid.models import DockerContainer, VmDomain
from homeassistant.components.unraid.switch import (
    DockerContainerSwitch,
    VirtualMachineSwitch,
    async_setup_entry,
)
from homeassistant.exceptions import HomeAssistantError

from .conftest import make_system_data


class TestDockerContainerSwitch:
    """Test Docker container switch."""

    def test_container_switch_creation(self) -> None:
        """Test Docker container switch creation."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
            image="nginx:latest",
            web_ui_url="https://tower/apps/web",
            icon_url="https://cdn/icons/web.png",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        # unique_id uses container NAME (stable) not ID (ephemeral)
        assert switch.unique_id == "test-uuid_container_switch_web"
        assert (
            switch.name == "Container web"
        )  # Should strip leading / and prefix with Container
        assert switch.device_info is not None

    def test_container_switch_is_on_when_running(self) -> None:
        """Test container switch is on when running."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
            image="nginx:latest",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.is_on is True

    def test_container_switch_is_off_when_stopped(self) -> None:
        """Test container switch is off when stopped."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="EXITED",
            image="nginx:latest",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.is_on is False

    def test_container_switch_attributes(self) -> None:
        """Test container switch extra attributes."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
            image="nginx:latest",
            web_ui_url="https://tower/apps/web",
            icon_url="https://cdn/icons/web.png",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        attrs = switch.extra_state_attributes
        assert attrs["image"] == "nginx:latest"
        assert attrs["status"] == "RUNNING"
        assert attrs["web_ui_url"] == "https://tower/apps/web"
        assert attrs["icon_url"] == "https://cdn/icons/web.png"

    def test_container_switch_attributes_filters_none(self) -> None:
        """Test container switch filters out None values from attributes."""
        container = DockerContainer(
            id="ct:1",
            name="/minimal",
            state="RUNNING",
            # image, webUiUrl, iconUrl are all None by default
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        attrs = switch.extra_state_attributes
        # Only status should be present (always set)
        assert attrs == {"status": "RUNNING"}
        assert "image" not in attrs
        assert "web_ui_url" not in attrs
        assert "icon_url" not in attrs

    def test_container_id_updates_after_container_recreate(self) -> None:
        """Test that container ID is updated when container is recreated.

        This is the key fix for issue #133 - when a container is updated,
        Docker creates a new container with a new ID but same name. The
        entity should continue to work with the new container.
        """
        # Initial container with original ID
        container_v1 = DockerContainer(
            id="ct:original-id-12345",
            name="/web",
            state="RUNNING",
            image="nginx:1.0",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container_v1])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container_v1,
        )

        # Verify initial state
        assert switch._container_id == "ct:original-id-12345"
        assert switch._container_name == "web"
        assert switch.unique_id == "test-uuid_container_switch_web"
        assert switch.is_on is True

        # Simulate container update - new container with NEW ID, same name
        container_v2 = DockerContainer(
            id="ct:new-id-67890",  # NEW ID after update
            name="/web",  # Same name
            state="RUNNING",
            image="nginx:2.0",  # Updated image
        )
        # Reset cache to force re-lookup
        switch._cache_data_id = None
        switch._cached_container = None
        coordinator.data = make_system_data(containers=[container_v2])

        # Access is_on to trigger lookup and ID update
        assert switch.is_on is True

        # Verify the container ID was updated
        assert switch._container_id == "ct:new-id-67890"
        # But unique_id remains stable (based on name)
        assert switch.unique_id == "test-uuid_container_switch_web"


class TestVirtualMachineSwitch:
    """Test VM switch."""

    def test_vm_switch_creation(self) -> None:
        """Test VM switch creation."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
            memory=4096,
            vcpu=4,
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        # unique_id uses VM NAME (stable) not ID (may be ephemeral)
        assert switch.unique_id == "test-uuid_vm_switch_Ubuntu"
        assert switch.name == "VM Ubuntu"  # Should prefix with VM

    def test_vm_switch_is_on_when_running(self) -> None:
        """Test VM switch is on when running."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
            memory=4096,
            vcpu=4,
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        assert switch.is_on is True

    def test_vm_switch_is_on_when_idle(self) -> None:
        """Test VM switch is on when idle."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="IDLE",
            memory=4096,
            vcpu=4,
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        assert switch.is_on is True

    def test_vm_switch_is_off_when_shut_down(self) -> None:
        """Test VM switch is off when shut down."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="SHUT_DOWN",
            memory=4096,
            vcpu=4,
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        assert switch.is_on is False

    def test_vm_switch_attributes(self) -> None:
        """Test VM switch extra attributes."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
            memory=4096,
            vcpu=4,
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        attrs = switch.extra_state_attributes
        assert attrs["state"] == "RUNNING"
        assert attrs["memory"] == 4096
        assert attrs["vcpu"] == 4

    def test_vm_switch_attributes_filters_none(self) -> None:
        """Test VM switch filters out None values from attributes."""
        vm = VmDomain(
            id="vm:1",
            name="Minimal",
            state="RUNNING",
            # memory and vcpu are None by default
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        attrs = switch.extra_state_attributes
        # Only state should be present (always set)
        assert attrs == {"state": "RUNNING"}
        assert "memory" not in attrs
        assert "vcpu" not in attrs

    def test_vm_switch_no_data(self) -> None:
        """Test VM switch when coordinator has no data."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = None
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        assert switch.is_on is False
        assert switch.extra_state_attributes == {}

    def test_vm_switch_vm_not_found(self) -> None:
        """Test VM switch when VM not found in coordinator data."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[])  # Empty VMs
        api_client = MagicMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_vm_turn_on_success(self) -> None:
        """Test successfully starting a VM."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="SHUTOFF",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()
        api_client.start_vm = AsyncMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        await switch.async_turn_on()
        api_client.start_vm.assert_called_once_with("vm:1")

    @pytest.mark.asyncio
    async def test_vm_turn_on_failure(self) -> None:
        """Test VM start failure raises HomeAssistantError."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="SHUTOFF",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()
        api_client.start_vm = AsyncMock(side_effect=Exception("Connection failed"))

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        with pytest.raises(HomeAssistantError, match="Failed to start VM"):
            await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_vm_turn_off_success(self) -> None:
        """Test successfully stopping a VM."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()
        api_client.stop_vm = AsyncMock()

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        await switch.async_turn_off()
        api_client.stop_vm.assert_called_once_with("vm:1")

    @pytest.mark.asyncio
    async def test_vm_turn_off_failure(self) -> None:
        """Test VM stop failure raises HomeAssistantError."""
        vm = VmDomain(
            id="vm:1",
            name="Ubuntu",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(vms=[vm])
        api_client = MagicMock()
        api_client.stop_vm = AsyncMock(side_effect=Exception("Permission denied"))

        switch = VirtualMachineSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            vm=vm,
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop VM"):
            await switch.async_turn_off()


class TestDockerContainerSwitchAsync:
    """Test Docker container switch async methods."""

    @pytest.mark.asyncio
    async def test_container_turn_on_success(self) -> None:
        """Test successfully starting a container."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="EXITED",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()
        api_client.start_container = AsyncMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        await switch.async_turn_on()
        api_client.start_container.assert_called_once_with("ct:1")

    @pytest.mark.asyncio
    async def test_container_turn_on_failure(self) -> None:
        """Test container start failure raises HomeAssistantError."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="EXITED",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()
        api_client.start_container = AsyncMock(
            side_effect=Exception("Docker API error")
        )

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        with pytest.raises(HomeAssistantError, match="Failed to start container"):
            await switch.async_turn_on()

    @pytest.mark.asyncio
    async def test_container_turn_off_success(self) -> None:
        """Test successfully stopping a container."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()
        api_client.stop_container = AsyncMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        await switch.async_turn_off()
        api_client.stop_container.assert_called_once_with("ct:1")

    @pytest.mark.asyncio
    async def test_container_turn_off_failure(self) -> None:
        """Test container stop failure raises HomeAssistantError."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()
        api_client.stop_container = AsyncMock(side_effect=Exception("Timeout"))

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        with pytest.raises(HomeAssistantError, match="Failed to stop container"):
            await switch.async_turn_off()

    def test_container_no_data(self) -> None:
        """Test container switch when coordinator has no data."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = None
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.is_on is False
        assert switch.extra_state_attributes == {}

    def test_container_not_found(self) -> None:
        """Test container switch when container not found in coordinator data."""
        container = DockerContainer(
            id="ct:1",
            name="/web",
            state="RUNNING",
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(containers=[])  # Empty containers
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.is_on is False


class TestSwitchAvailability:
    """Test switch availability."""

    def test_available_true(self) -> None:
        """Test switch is available when coordinator succeeds."""
        container = DockerContainer(id="ct:1", name="/web", state="RUNNING")
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.last_update_success = True
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.available is True

    def test_available_false(self) -> None:
        """Test switch is not available when coordinator fails."""
        container = DockerContainer(id="ct:1", name="/web", state="RUNNING")
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.last_update_success = False
        coordinator.data = make_system_data(containers=[container])
        api_client = MagicMock()

        switch = DockerContainerSwitch(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid="test-uuid",
            server_name="test-server",
            container=container,
        )

        assert switch.available is False


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_creates_container_switches(self, hass) -> None:
        """Test setup creates Docker container switches."""
        container = DockerContainer(id="ct:1", name="/web", state="RUNNING")

        system_coordinator = MagicMock()
        system_coordinator.data = make_system_data(containers=[container])

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=MagicMock(),
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        assert len(added_entities) == 1
        assert isinstance(added_entities[0], DockerContainerSwitch)

    @pytest.mark.asyncio
    async def test_setup_creates_vm_switches(self, hass) -> None:
        """Test setup creates VM switches."""
        vm = VmDomain(id="vm:1", name="Ubuntu", state="RUNNING")

        system_coordinator = MagicMock()
        system_coordinator.data = make_system_data(vms=[vm])

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=MagicMock(),
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        assert len(added_entities) == 1
        assert isinstance(added_entities[0], VirtualMachineSwitch)

    @pytest.mark.asyncio
    async def test_setup_no_containers_or_vms(self, hass) -> None:
        """Test setup handles no containers or VMs."""
        system_coordinator = MagicMock()
        system_coordinator.data = make_system_data()  # Empty data

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=MagicMock(),
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        assert len(added_entities) == 0

    @pytest.mark.asyncio
    async def test_setup_no_coordinator_data(self, hass) -> None:
        """Test setup handles None coordinator data."""
        system_coordinator = MagicMock()
        system_coordinator.data = None

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=MagicMock(),
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        assert len(added_entities) == 0
