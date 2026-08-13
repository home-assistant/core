"""Unit tests for switch.py."""

from __future__ import annotations

from homeassistant.components.truenas_ce.switch import (
    TrueNASCloudsyncSwitch,
    TrueNASCronjobSwitch,
    TrueNASServiceSwitch,
)
from homeassistant.components.truenas_ce.switch_types import (
    TrueNASSwitchEntityDescription,
)

from ._fakes import make_coordinator

_SERVICE_DESC = TrueNASSwitchEntityDescription(
    key="service_switch", name=None, data_path="service", data_is_on="running"
)
_CLOUDSYNC_DESC = TrueNASSwitchEntityDescription(
    key="cloudsync_switch", name=None, data_path="cloudsync", data_is_on="enabled"
)
_CRONJOB_DESC = TrueNASSwitchEntityDescription(
    key="cronjob_switch", name=None, data_path="cronjob", data_is_on="enabled"
)


def test_service_switch_is_on_true() -> None:
    coordinator = make_coordinator(
        data={"service": {"s1": {"running": True, "service": "ssh"}}}
    )
    switch = TrueNASServiceSwitch(coordinator, _SERVICE_DESC, "s1")
    assert switch.is_on is True


def test_service_switch_is_on_false_when_missing() -> None:
    coordinator = make_coordinator(data={"service": {"s1": {"service": "ssh"}}})
    switch = TrueNASServiceSwitch(coordinator, _SERVICE_DESC, "s1")
    assert switch.is_on is False


async def test_service_switch_turn_on_calls_service_start_and_refreshes() -> None:
    coordinator = make_coordinator(data={"service": {"s1": {"service": "ssh"}}})
    switch = TrueNASServiceSwitch(coordinator, _SERVICE_DESC, "s1")
    await switch.async_turn_on()
    coordinator.api.query.assert_awaited_once_with("service.start", ["ssh"])
    coordinator.async_request_refresh.assert_awaited_once()


async def test_service_switch_turn_off_calls_service_stop_and_refreshes() -> None:
    coordinator = make_coordinator(data={"service": {"s1": {"service": "ssh"}}})
    switch = TrueNASServiceSwitch(coordinator, _SERVICE_DESC, "s1")
    await switch.async_turn_off()
    coordinator.api.query.assert_awaited_once_with("service.stop", ["ssh"])
    coordinator.async_request_refresh.assert_awaited_once()


async def test_cloudsync_switch_turn_on_calls_update_method() -> None:
    coordinator = make_coordinator(data={"cloudsync": {"c1": {"id": 3}}})
    switch = TrueNASCloudsyncSwitch(coordinator, _CLOUDSYNC_DESC, "c1")
    await switch.async_turn_on()
    coordinator.api.query.assert_awaited_once_with(
        "cloudsync.update", [3, {"enabled": True}]
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_cloudsync_switch_turn_off_calls_update_method() -> None:
    coordinator = make_coordinator(data={"cloudsync": {"c1": {"id": 3}}})
    switch = TrueNASCloudsyncSwitch(coordinator, _CLOUDSYNC_DESC, "c1")
    await switch.async_turn_off()
    coordinator.api.query.assert_awaited_once_with(
        "cloudsync.update", [3, {"enabled": False}]
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_cronjob_switch_turn_on_calls_update_method() -> None:
    coordinator = make_coordinator(data={"cronjob": {"j1": {"id": 9}}})
    switch = TrueNASCronjobSwitch(coordinator, _CRONJOB_DESC, "j1")
    await switch.async_turn_on()
    coordinator.api.query.assert_awaited_once_with(
        "cronjob.update", [9, {"enabled": True}]
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_cronjob_switch_turn_off_calls_update_method() -> None:
    coordinator = make_coordinator(data={"cronjob": {"j1": {"id": 9}}})
    switch = TrueNASCronjobSwitch(coordinator, _CRONJOB_DESC, "j1")
    await switch.async_turn_off()
    coordinator.api.query.assert_awaited_once_with(
        "cronjob.update", [9, {"enabled": False}]
    )
    coordinator.async_request_refresh.assert_awaited_once()
