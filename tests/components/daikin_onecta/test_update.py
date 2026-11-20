"""Tests for Daikin Onecta firmware update entities."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from daikin_onecta import OnectaConnectionError
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import MockOnectaClient
from .platform_helpers import (
    _async_fire_coordinator_update,
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)

LIVING_ROOM_FIRMWARE_UPDATE_ENTITY_ID = "update.living_room_firmware_update"


async def test_firmware_install_executes_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """The update service executes the typed firmware-install command."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
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
        is True
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert (
        hass.states.get(state.entity_id).attributes[
            UpdateEntityStateAttribute.IN_PROGRESS
        ]
        is False
    )

    gateway_point = gateways[0].management_point(gateways[0].gateway_embedded_id)
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
    gateways = _load_gateway_devices("dx4_firmwareavailable")
    point = gateways[0].management_point(gateways[0].gateway_embedded_id)
    assert point is not None
    point.firmware_update_status = Characteristic(value="idle")
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

    async def read_gateways() -> list[GatewayDevice]:
        pending_at_poll.append(entity._pending_install)
        poll_started.set()
        await finish_poll.wait()
        return gateways

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

    point.firmware_update_status = Characteristic(value="in-progress")
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
    coordinator.async_execute_command = _execute_typed_command(config_entry)

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


@pytest.mark.usefixtures("mock_onecta_client")
async def test_firmware_install_schedules_refresh_after_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Refresh cloud state shortly after a successful firmware install."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
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
            ServiceValidationError,
            "firmware_install_unavailable",
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Clear update state through HA when a gateway stops reporting firmware."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
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
