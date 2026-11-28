"""Tests for the GARDENA smart local coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from gardena_smart_local_api.client import (
    DeviceManager,
    IncludableDevice,
    InclusionError,
    RequestError,
)
from gardena_smart_local_api.devices import Device
from gardena_smart_local_api.devices.irrigation import Gen1WaterControl
from gardena_smart_local_api.devices.mowers import Gen2Mower
from gardena_smart_local_api.messages import IngressMessageList
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
    CONF_FINGERPRINT: "ab" * 32,
}


@pytest.fixture
async def coordinator(hass: HomeAssistant) -> GardenaSmartLocalCoordinator:
    """Return a coordinator that is not connected to a gateway."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    return GardenaSmartLocalCoordinator(
        hass,
        entry,
        MOCK_DATA[CONF_HOST],
        MOCK_DATA[CONF_PORT],
        MOCK_DATA[CONF_PASSWORD],
        MOCK_DATA[CONF_FINGERPRINT],
    )


def _includable(instance_id: str, device_class: type[Device]) -> IncludableDevice:
    return IncludableDevice(
        instance_id=instance_id,
        service="some-service",
        device_id=f"device-{instance_id}",
        name=f"Device {instance_id}",
        device_class=device_class,
    )


async def test_manager_is_set_up_for_the_gateway(hass: HomeAssistant) -> None:
    """The manager pins the certificate and reports back to the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gardena_smart_local.coordinator.DeviceManager"
    ) as manager_class:
        coordinator = GardenaSmartLocalCoordinator(
            hass,
            entry,
            MOCK_DATA[CONF_HOST],
            MOCK_DATA[CONF_PORT],
            MOCK_DATA[CONF_PASSWORD],
            MOCK_DATA[CONF_FINGERPRINT],
        )

    manager_class.assert_called_once_with(
        MOCK_DATA[CONF_HOST],
        MOCK_DATA[CONF_PORT],
        MOCK_DATA[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        fingerprint=MOCK_DATA[CONF_FINGERPRINT],
        on_devices_changed=coordinator._on_devices_changed,
        on_disconnect=coordinator._on_disconnect,
        on_auth_failed=coordinator._on_auth_failed,
    )
    assert coordinator.manager is manager_class.return_value


async def test_rejected_password_starts_reauthentication(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Once the manager gives up on the password, the user is asked for a new one."""
    with patch.object(coordinator.config_entry, "async_start_reauth") as start_reauth:
        coordinator._on_auth_failed()

    start_reauth.assert_called_once_with(coordinator.hass)


async def test_uri_and_connected_come_from_the_manager(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The coordinator reports what the manager knows about the connection."""
    assert coordinator.uri == "wss://192.168.1.100:8443"

    for connected in (True, False):
        with patch.object(
            DeviceManager, "connected", new_callable=PropertyMock
        ) as manager_connected:
            manager_connected.return_value = connected
            assert coordinator.connected is connected


async def test_connect_and_disconnect_use_the_manager(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Connecting and disconnecting is left to the manager."""
    with (
        patch.object(coordinator.manager, "connect", AsyncMock()) as connect,
        patch.object(coordinator.manager, "disconnect", AsyncMock()) as disconnect,
    ):
        await coordinator.async_connect()
        await coordinator.async_disconnect()

    connect.assert_awaited_once_with()
    disconnect.assert_awaited_once_with()


async def test_changed_devices_are_published(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The entities get the devices of the manager when some of them changed."""
    device = MagicMock(id="dev-1")
    coordinator.manager._devices = {"dev-1": device}

    coordinator._on_devices_changed(frozenset({"dev-1"}))

    assert coordinator.data == {"dev-1": device}


async def test_lost_connection_updates_the_entities(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Entities re-check their availability when the connection drops."""
    with patch.object(coordinator, "async_update_listeners") as update_listeners:
        coordinator._on_disconnect()

    update_listeners.assert_called_once_with()


async def test_only_supported_devices_can_be_included(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Sensors and mowers have no entities here, so they are not offered."""
    water_control = _includable("1", Gen1WaterControl)
    mower = _includable("2", Gen2Mower)

    with patch.object(
        DeviceManager,
        "includable_devices",
        new_callable=PropertyMock,
        return_value={"1": water_control, "2": mower},
    ):
        assert coordinator.includable_devices == {"1": water_control}


async def test_include_returns_the_id_of_the_included_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The caller publishes the new device itself, so the manager stays quiet."""
    include = AsyncMock(return_value=MagicMock(id="device-1"))

    with (
        patch.object(
            DeviceManager,
            "includable_devices",
            new_callable=PropertyMock,
            return_value={"1": _includable("1", Gen1WaterControl)},
        ),
        patch.object(coordinator.manager, "include_device", include),
    ):
        assert await coordinator.async_include_device("1") == "device-1"

    include.assert_awaited_once_with("1", notify=False)


async def test_unsupported_device_is_not_included(
    coordinator: GardenaSmartLocalCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device without entities is not included, as removing it would reset it."""
    include = AsyncMock()

    with (
        patch.object(
            DeviceManager,
            "includable_devices",
            new_callable=PropertyMock,
            return_value={"2": _includable("2", Gen2Mower)},
        ),
        patch.object(coordinator.manager, "include_device", include),
    ):
        assert await coordinator.async_include_device("2") is None

    include.assert_not_awaited()
    assert "No supported includable device" in caplog.text


async def test_failed_inclusion_reports_none(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The config flow gets None instead of the error."""
    with (
        patch.object(
            DeviceManager,
            "includable_devices",
            new_callable=PropertyMock,
            return_value={"1": _includable("1", Gen1WaterControl)},
        ),
        patch.object(
            coordinator.manager,
            "include_device",
            AsyncMock(side_effect=InclusionError("not accepted")),
        ),
    ):
        assert await coordinator.async_include_device("1") is None


async def test_exclude_success(coordinator: GardenaSmartLocalCoordinator) -> None:
    """A device that the gateway excluded is reported as excluded."""
    exclude = AsyncMock()

    with patch.object(coordinator.manager, "exclude_device", exclude):
        assert await coordinator.async_exclude_device("dev-1") is True

    exclude.assert_awaited_once_with("dev-1")


@pytest.mark.parametrize(
    "error",
    [
        RequestError("rejected", IngressMessageList([])),
        TimeoutError(),
        ConnectionError(),
    ],
)
async def test_exclude_failure_reports_false(
    coordinator: GardenaSmartLocalCoordinator, error: Exception
) -> None:
    """The caller learns that the device is still paired with the gateway."""
    with patch.object(
        coordinator.manager, "exclude_device", AsyncMock(side_effect=error)
    ):
        assert await coordinator.async_exclude_device("dev-1") is False


async def test_send_command_uses_the_manager(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Commands go through the manager, which holds back the intermediate states."""
    replies = IngressMessageList([])
    send = AsyncMock(return_value=replies)
    request = MagicMock()

    with patch.object(coordinator.manager, "send_command", send):
        result = await coordinator.async_send_command("dev-1", request, 5)

    assert result is replies
    send.assert_awaited_once_with("dev-1", request, 5)


async def test_update_returns_the_devices_of_the_manager(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Updates are pushed, so a refresh only hands out what the manager knows."""
    device = MagicMock(id="dev-1")
    coordinator.manager._devices = {"dev-1": device}

    assert await coordinator._async_update_data() == {"dev-1": device}
