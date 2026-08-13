"""Unit tests for binary_sensor.py."""

from __future__ import annotations

from homeassistant.components.truenas_ce.binary_sensor import (
    TrueNASAppBinarySensor,
    TrueNASBinarySensor,
    TrueNASContainerBinarySensor,
    TrueNASServiceBinarySensor,
    TrueNASVMBinarySensor,
)
from homeassistant.components.truenas_ce.binary_sensor_types import (
    TrueNASBinarySensorEntityDescription,
)
from homeassistant.components.truenas_ce.const import VIRT_INSTANCE_STOP_OPTIONS

from ._fakes import make_coordinator

_DESC = TrueNASBinarySensorEntityDescription(
    key="k", name="N", data_path="vm", data_is_on="running"
)


def _make(cls, data: dict, path: str = "vm"):
    description = TrueNASBinarySensorEntityDescription(
        key="k", name="N", data_path=path, data_is_on="running"
    )
    coordinator = make_coordinator(data={path: {"o1": data}})
    return cls(coordinator, description, "o1")


def test_is_on_true() -> None:
    sensor = _make(TrueNASBinarySensor, {"running": True})
    assert sensor.is_on is True


def test_is_on_none_when_missing() -> None:
    sensor = _make(TrueNASBinarySensor, {})
    assert sensor.is_on is None


def test_icon_always_none() -> None:
    """Icons are resolved via icons.json translations, not a backend property."""
    sensor = _make(TrueNASBinarySensor, {"running": True})
    assert sensor.icon is None


# ---------------------------
#   TrueNASVMBinarySensor
# ---------------------------
def _make_vm(data: dict) -> TrueNASVMBinarySensor:
    return _make(TrueNASVMBinarySensor, {"id": 1, "name": "vm1", **data}, path="vm")


async def test_vm_start_invalid_state_logs_and_returns() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.return_value = {"status": {}}
    await vm.start()
    vm.coordinator.api.query.assert_awaited_once()


async def test_vm_start_not_stopped_returns() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.return_value = {"status": {"state": "RUNNING"}}
    await vm.start()
    vm.coordinator.api.query.assert_awaited_once_with("vm.get_instance", [1])


async def test_vm_start_success() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.side_effect = [{"status": {"state": "STOPPED"}}, None]
    await vm.start(overcommit=True)
    assert vm.coordinator.api.query.await_count == 2
    vm.coordinator.api.query.assert_awaited_with("vm.start", [1, {"overcommit": True}])


async def test_vm_stop_invalid_state_logs_and_returns() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.return_value = None
    await vm.stop()
    vm.coordinator.api.query.assert_awaited_once()


async def test_vm_stop_not_running_returns() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.return_value = {"status": {"state": "STOPPED"}}
    await vm.stop()
    vm.coordinator.api.query.assert_awaited_once()


async def test_vm_stop_success() -> None:
    vm = _make_vm({})
    vm.coordinator.api.query.side_effect = [{"status": {"state": "RUNNING"}}, None]
    await vm.stop()
    vm.coordinator.api.query.assert_awaited_with(
        "vm.stop", [1, {"force": True, "force_after_timeout": True}]
    )


async def test_vm_restart_always_calls_and_refreshes() -> None:
    vm = _make_vm({})
    await vm.restart()
    vm.coordinator.api.query.assert_awaited_once_with("vm.restart", [1])
    vm.coordinator.async_request_refresh.assert_awaited_once()


# ---------------------------
#   TrueNASContainerBinarySensor
# ---------------------------
def _make_container(data: dict | None = None) -> TrueNASContainerBinarySensor:
    return _make(
        TrueNASContainerBinarySensor,
        {"id": "c1", "name": "ct1", **(data or {})},
        path="container",
    )


async def test_container_current_status_returns_status() -> None:
    ct = _make_container()
    ct.coordinator.api.query.return_value = [{"status": "RUNNING"}]
    assert await ct._current_status() == "RUNNING"


async def test_container_current_status_handles_query_exception() -> None:
    ct = _make_container()
    ct.coordinator.api.query.side_effect = RuntimeError("boom")
    assert await ct._current_status() is None


async def test_container_start_already_running_skips() -> None:
    ct = _make_container()
    ct.coordinator.api.query.return_value = [{"status": "RUNNING"}]
    await ct.start()
    ct.coordinator.api.query.assert_awaited_once()


async def test_container_start_success() -> None:
    ct = _make_container()
    ct.coordinator.api.query.side_effect = [[{"status": "STOPPED"}], None]
    await ct.start()
    ct.coordinator.api.query.assert_awaited_with("virt.instance.start", ["c1"])
    ct.coordinator.async_request_refresh.assert_awaited_once()


async def test_container_stop_not_running_skips() -> None:
    ct = _make_container()
    ct.coordinator.api.query.return_value = [{"status": "STOPPED"}]
    await ct.stop()
    ct.coordinator.api.query.assert_awaited_once()


async def test_container_stop_success() -> None:
    ct = _make_container()
    ct.coordinator.api.query.side_effect = [[{"status": "RUNNING"}], None]
    await ct.stop()
    ct.coordinator.api.query.assert_awaited_with(
        "virt.instance.stop", ["c1", VIRT_INSTANCE_STOP_OPTIONS]
    )
    ct.coordinator.async_request_refresh.assert_awaited_once()


async def test_container_restart_always_calls_and_refreshes() -> None:
    ct = _make_container()
    await ct.restart()
    ct.coordinator.api.query.assert_awaited_once_with(
        "virt.instance.restart", ["c1", VIRT_INSTANCE_STOP_OPTIONS]
    )
    ct.coordinator.async_request_refresh.assert_awaited_once()


# ---------------------------
#   TrueNASServiceBinarySensor
# ---------------------------
def _make_service(data: dict | None = None) -> TrueNASServiceBinarySensor:
    return _make(
        TrueNASServiceBinarySensor,
        {"id": 4, "service": "ssh", **(data or {})},
        path="service",
    )


async def test_service_start_invalid_state_returns() -> None:
    svc = _make_service()
    svc.coordinator.api.query.return_value = [{}]
    await svc.start()
    svc.coordinator.api.query.assert_awaited_once()


async def test_service_start_not_stopped_returns() -> None:
    svc = _make_service()
    svc.coordinator.api.query.return_value = [{"state": "RUNNING"}]
    await svc.start()
    svc.coordinator.api.query.assert_awaited_once()


async def test_service_start_success() -> None:
    svc = _make_service()
    svc.coordinator.api.query.side_effect = [[{"state": "STOPPED"}], None]
    await svc.start()
    svc.coordinator.api.query.assert_awaited_with("service.start", ["ssh"])
    svc.coordinator.async_refresh.assert_awaited_once()


async def test_service_stop_not_running_returns() -> None:
    svc = _make_service()
    svc.coordinator.api.query.return_value = [{"state": "STOPPED"}]
    await svc.stop()
    svc.coordinator.api.query.assert_awaited_once()


async def test_service_stop_success() -> None:
    svc = _make_service()
    svc.coordinator.api.query.side_effect = [[{"state": "RUNNING"}], None]
    await svc.stop()
    svc.coordinator.api.query.assert_awaited_with("service.stop", ["ssh"])
    svc.coordinator.async_refresh.assert_awaited_once()


async def test_service_restart_stopped_returns() -> None:
    svc = _make_service()
    svc.coordinator.api.query.return_value = [{"state": "STOPPED"}]
    await svc.restart()
    svc.coordinator.api.query.assert_awaited_once()


async def test_service_restart_success() -> None:
    svc = _make_service()
    svc.coordinator.api.query.side_effect = [[{"state": "RUNNING"}], None]
    await svc.restart()
    svc.coordinator.api.query.assert_awaited_with("service.restart", ["ssh"])
    svc.coordinator.async_refresh.assert_awaited_once()


async def test_service_reload_stopped_returns() -> None:
    svc = _make_service()
    svc.coordinator.api.query.return_value = [{"state": "STOPPED"}]
    await svc.reload()
    svc.coordinator.api.query.assert_awaited_once()


async def test_service_reload_success() -> None:
    svc = _make_service()
    svc.coordinator.api.query.side_effect = [[{"state": "RUNNING"}], None]
    await svc.reload()
    svc.coordinator.api.query.assert_awaited_with("service.reload", ["ssh"])
    svc.coordinator.async_refresh.assert_awaited_once()


# ---------------------------
#   TrueNASAppBinarySensor
# ---------------------------
def _make_app(data: dict | None = None) -> TrueNASAppBinarySensor:
    return _make(
        TrueNASAppBinarySensor, {"id": "a1", "name": "app1", **(data or {})}, path="app"
    )


async def test_app_start_invalid_state_returns() -> None:
    app = _make_app()
    app.coordinator.api.query.return_value = None
    await app.start()
    app.coordinator.api.query.assert_awaited_once()


async def test_app_start_already_running_returns() -> None:
    app = _make_app()
    app.coordinator.api.query.return_value = {"state": "RUNNING"}
    await app.start()
    app.coordinator.api.query.assert_awaited_once()


async def test_app_start_success() -> None:
    app = _make_app()
    app.coordinator.api.query.side_effect = [{"state": "STOPPED"}, None]
    await app.start()
    app.coordinator.api.query.assert_awaited_with("app.start", ["a1"])


async def test_app_stop_invalid_state_returns() -> None:
    app = _make_app()
    app.coordinator.api.query.return_value = None
    await app.stop()
    app.coordinator.api.query.assert_awaited_once()


async def test_app_stop_not_running_returns() -> None:
    app = _make_app()
    app.coordinator.api.query.return_value = {"state": "STOPPED"}
    await app.stop()
    app.coordinator.api.query.assert_awaited_once()


async def test_app_stop_success() -> None:
    app = _make_app()
    app.coordinator.api.query.side_effect = [{"state": "RUNNING"}, None]
    await app.stop()
    app.coordinator.api.query.assert_awaited_with("app.stop", ["a1"])
