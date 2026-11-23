"""Tests for Daikin Onecta firmware update entities."""

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from daikin_onecta import OnectaConnectionError
from daikin_onecta.client import OnectaClient
from daikin_onecta.models import Characteristic, GatewayDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE as CLIMATE_SERVICE_SET_TEMPERATURE,
    ClimateServiceArgument,
)
from homeassistant.components.daikin_onecta.update import DaikinFirmwareUpdateEntity
from homeassistant.components.update import (
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
    UpdateEntityStateAttribute,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MockOnectaClient
from .platform_helpers import (
    _async_fire_coordinator_update,
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)

LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID = "update.living_room_firmware_update"


async def test_software_versions_only_update_device_metadata(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not create update entities for points that only report versions."""
    await _async_setup_fixture(hass, config_entry, "altherma")

    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    ]


async def test_firmware_install_executes_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """The update service executes the typed firmware-install command."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID},
        blocking=True,
    )

    config_entry.runtime_data.async_execute_command.assert_awaited_once()
    state = hass.states.get(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True

    coordinator = config_entry.runtime_data
    coordinator.async_update_listeners()
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is True
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        CLIMATE_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_room_temperature",
            ClimateServiceArgument.TEMPERATURE: 25,
        },
        blocking=True,
    )
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is True
    )

    # Three fresh polls without status or version evidence may still be stale.
    gateways = _load_gateway_devices("dx4_firmwareavailable")
    mock_onecta_client.get_gateway_devices.return_value = gateways
    gateway_point = gateways[0].management_point(gateways[0].gateway_embedded_id)
    assert gateway_point is not None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is True
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is True
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is False
    )

    gateway_point.firmware_update_status = Characteristic(value="in-progress")
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is True
    )

    gateway_point.firmware_update_status = None
    gateway_point.firmware_version = Characteristic(value="new-version")
    gateway_point.software_version = Characteristic(value="new-version")
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is False
    )
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.INSTALLED_VERSION
        ]
        == "new-version"
    )


async def test_firmware_pending_install_survives_missing_installed_version(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep an install pending when a poll omits the installed version."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    entity_id = LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID
    entity = hass.data[UPDATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinFirmwareUpdateEntity)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert entity._pending_install is not None

    gateways = _load_gateway_devices("dx4_firmwareavailable")
    gateway_embedded_id = gateways[0].gateway_embedded_id
    assert gateway_embedded_id is not None
    point = gateways[0].management_point(gateway_embedded_id)
    assert point is not None
    point.firmware_version = None
    point.software_version = None
    mock_onecta_client.get_gateway_devices.return_value = gateways

    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity._pending_install is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True

    point.firmware_version = Characteristic(value="new-version")
    point.software_version = Characteristic(value="new-version")
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity._pending_install is None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is False


async def test_firmware_entity_available_without_installed_version(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep firmware status and offers available if Daikin omits its version."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    gateway = device.device.management_point(device.device.gateway_embedded_id)
    assert gateway is not None
    gateway.firmware_version = None
    gateway.software_version = None

    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"
    assert state.attributes[UpdateEntityStateAttribute.INSTALLED_VERSION] is None


async def test_firmware_install_records_pending_state_before_waiting_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Publish pending install state before the cloud write and stale polls."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    entity_id = LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID
    entity = hass.data[UPDATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinFirmwareUpdateEntity)
    requested_sequence = coordinator.cloud_update_sequence
    installed_version = entity.installed_version
    missing_version_gateways = _load_gateway_devices("dx4_firmwareavailable")
    missing_version_point = missing_version_gateways[0].management_point(
        missing_version_gateways[0].gateway_embedded_id
    )
    assert missing_version_point is not None
    missing_version_point.firmware_update_status = Characteristic(value="idle")
    missing_version_point.firmware_version = None
    missing_version_point.software_version = None
    original_gateways = _load_gateway_devices("dx4_firmwareavailable")
    original_point = original_gateways[0].management_point(
        original_gateways[0].gateway_embedded_id
    )
    assert original_point is not None
    original_point.firmware_update_status = Characteristic(value="idle")
    poll_started = asyncio.Event()
    finish_poll = asyncio.Event()
    install_started = asyncio.Event()
    finish_install = asyncio.Event()
    pending_during_install: list[tuple[int, str | None, int] | None] = []
    pending_at_poll: list[tuple[int, str | None, int] | None] = []

    async def install(
        _gateway_id: str, _management_point_id: str, _resource: str
    ) -> None:
        pending_during_install.append(entity._pending_install)
        install_started.set()
        await finish_install.wait()

    read_count = 0

    async def read_gateways() -> list[GatewayDevice]:
        nonlocal read_count
        read_count += 1
        pending_at_poll.append(entity._pending_install)
        poll_started.set()
        await finish_poll.wait()
        if read_count == 1:
            return missing_version_gateways
        return original_gateways

    with (
        patch.object(coordinator.client, "put_management_point", side_effect=install),
        patch.object(
            coordinator.client, "get_gateway_devices", side_effect=read_gateways
        ),
        # Exercise the waiting poll without relying on the post-write cooldown.
        patch(
            "homeassistant.components.daikin_onecta.coordinator._POST_WRITE_COOLDOWN",
            timedelta(0),
        ),
    ):
        assert coordinator.update_interval is not None
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await poll_started.wait()
        install_task = hass.async_create_task(
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        )
        await asyncio.sleep(0)
        assert entity._pending_install == (
            requested_sequence,
            installed_version,
            requested_sequence + 3,
        )
        assert not install_started.is_set()
        finish_poll.set()
        await install_started.wait()
        assert pending_during_install == [
            (requested_sequence, installed_version, requested_sequence + 3)
        ]
        finish_install.set()
        await install_task

        # Query the stale cloud model after the install service returns.
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert pending_at_poll == [
        None,
        (
            requested_sequence + 1,
            installed_version,
            requested_sequence + 1 + 3,
        ),
    ]
    assert coordinator.cloud_update_sequence == requested_sequence + 2
    assert entity._pending_install == (
        requested_sequence + 1,
        installed_version,
        requested_sequence + 1 + 3,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert (
        state.attributes[UpdateEntityStateAttribute.INSTALLED_VERSION]
        == installed_version
    )
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True

    original_point.firmware_update_status = Characteristic(value="in-progress")
    with patch.object(
        coordinator.client, "get_gateway_devices", side_effect=read_gateways
    ):
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert entity._pending_install is None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True


async def test_firmware_pending_install_survives_failed_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep an install pending through a failed poll until confirmation."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    entity_id = LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID
    entity = hass.data[UPDATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinFirmwareUpdateEntity)
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert entity._pending_install is not None

    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity._pending_install is not None
    assert entity.in_progress
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


async def test_firmware_pending_install_keeps_baseline_when_version_is_missing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep the pre-install version when a poll omits it during the request."""
    original_devices = _load_gateway_devices("dx4_firmwareavailable")
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    entity = hass.data[UPDATE_DOMAIN].get_entity(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert isinstance(entity, DaikinFirmwareUpdateEntity)
    installed_version = entity.installed_version

    missing_version_devices = deepcopy(original_devices)
    gateway = missing_version_devices[0].gateway_management_point
    assert gateway is not None
    gateway.firmware_version = None
    mock_onecta_client.get_gateway_devices.return_value = missing_version_devices

    async def poll_during_install(
        _command: Callable[[OnectaClient], Awaitable[None]],
    ) -> bool:
        await _async_fire_coordinator_update(hass, coordinator, freezer)
        return True

    coordinator.async_execute_command = AsyncMock(side_effect=poll_during_install)
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID},
        blocking=True,
    )

    assert entity.installed_version is None
    assert entity._pending_install is not None
    assert entity._pending_install[1] == installed_version

    mock_onecta_client.get_gateway_devices.return_value = original_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert entity.installed_version == installed_version
    assert entity._pending_install is not None


@pytest.mark.usefixtures("mock_onecta_client")
async def test_firmware_install_schedules_refresh_after_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Refresh cloud state shortly after a successful firmware install."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    refresh = AsyncMock()
    coordinator.async_refresh = refresh

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID},
        blocking=True,
    )

    refresh.assert_not_awaited()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    refresh.assert_awaited_once_with()


async def test_failed_firmware_install_clears_pending_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A failed HA install service leaves no optimistic progress state."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.async_execute_command = AsyncMock(return_value=False)
    entity_id = LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is False
    assert state.attributes["supported_features"] == UpdateEntityFeature.INSTALL


async def test_cancelled_firmware_install_clears_pending_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Clear optimistic install state when its command is cancelled."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = AsyncMock(side_effect=asyncio.CancelledError)
    entity = hass.data[UPDATE_DOMAIN].get_entity(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert isinstance(entity, DaikinFirmwareUpdateEntity)

    with pytest.raises(asyncio.CancelledError):
        await entity.async_install(None, backup=False)

    assert entity._pending_install is None
    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is False


async def test_failed_firmware_install_preserves_reported_progress(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep firmware-reported progress support after an install command fails."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_point(gateway.device.gateway_embedded_id)
    assert point is not None
    point.firmware_update_status = Characteristic(value="in-progress")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    coordinator.async_execute_command = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True
    assert state.attributes["supported_features"] == (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )


@pytest.mark.parametrize(
    ("update_supported", "expected_error", "translation_key"),
    [
        pytest.param(
            False, HomeAssistantError, "service_not_supported", id="unsupported"
        ),
        pytest.param(
            True,
            HomeAssistantError,
            "service_not_supported",
            id="missing-firmware-id",
        ),
    ],
)
async def test_firmware_install_rejects_unavailable_firmware(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    update_supported: bool,
    expected_error: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Reject an install service if Daikin offers no supported firmware ID."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    execute = AsyncMock(return_value=True)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_point(gateway.device.gateway_embedded_id)
    assert point is not None
    assert point.is_firmware_update_supported is not None
    assert point.firmware_update is not None
    point.is_firmware_update_supported.value = update_supported
    point.firmware_update.value.pop("id")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    entity = hass.data[UPDATE_DOMAIN].get_entity(LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID)
    assert entity is not None
    assert not entity.supported_features & UpdateEntityFeature.INSTALL

    with pytest.raises(expected_error) as err:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    execute.assert_not_awaited()


async def test_firmware_state_clears_when_firmware_disappears(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Clear update state through HA when a gateway stops reporting firmware."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    entity_id = LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[UpdateEntityStateAttribute.IN_PROGRESS] is True

    gateway = next(iter(config_entry.runtime_data.data.values()))
    point = gateway.device.management_point(gateway.device.gateway_embedded_id)
    assert point is not None
    point.firmware_version = None
    point.software_version = None
    point.is_firmware_update_supported = None
    point.firmware_update = None
    point.firmware_update_status = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
