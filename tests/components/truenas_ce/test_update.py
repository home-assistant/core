"""Unit tests for update.py."""

from __future__ import annotations

import pytest

from homeassistant.components.truenas_ce.update import TrueNASAppUpdate, TrueNASUpdate
from homeassistant.components.truenas_ce.update_types import (
    TrueNASUpdateEntityDescription,
)
from homeassistant.exceptions import HomeAssistantError

from ._fakes import make_coordinator

_SYSTEM_DESC = TrueNASUpdateEntityDescription(
    key="system_update", name=None, data_path="system_info", title="TrueNAS"
)
_APP_DESC = TrueNASUpdateEntityDescription(key="app_update", name=None, data_path="app")


def _make_system_update(data: dict | None = None) -> TrueNASUpdate:
    coordinator = make_coordinator(data={"system_info": {**data} if data else {}})
    return TrueNASUpdate(coordinator, _SYSTEM_DESC)


def _make_app_update(data: dict | None = None) -> TrueNASAppUpdate:
    coordinator = make_coordinator(data={"app": {"a1": (data or {})}})
    return TrueNASAppUpdate(coordinator, _APP_DESC, "a1")


def test_system_update_installed_and_latest_version() -> None:
    update = _make_system_update({"version": "25.10.4", "update_version": "25.10.5"})
    assert update.installed_version == "25.10.4"
    assert update.latest_version == "25.10.5"


def test_system_update_in_progress_and_percentage() -> None:
    update = _make_system_update({"update_state": "RUNNING", "update_progress": 42})
    assert update.in_progress is True
    assert update.update_percentage == 42


def test_system_update_not_running_has_no_percentage() -> None:
    update = _make_system_update({"update_state": "IDLE"})
    assert update.in_progress is False
    assert update.update_percentage is None


async def test_system_update_async_install_success() -> None:
    update = _make_system_update({})
    update.coordinator.supports_update_run.return_value = False
    update.coordinator.api.query.return_value = 555
    await update.async_install(version=None, backup=False)
    update.coordinator.api.query.assert_awaited_once_with(
        "update.update", {"reboot": True}
    )
    assert update._data["update_jobid"] == 555
    update.coordinator.async_refresh.assert_awaited_once()


async def test_system_update_async_install_uses_update_run_on_2510_plus() -> None:
    update = _make_system_update({})
    update.coordinator.supports_update_run.return_value = True
    update.coordinator.api.query.return_value = 555
    await update.async_install(version=None, backup=False)
    update.coordinator.api.query.assert_awaited_once_with(
        "update.run", {"reboot": True}
    )
    assert update._data["update_jobid"] == 555


async def test_system_update_async_install_failure_raises() -> None:
    update = _make_system_update({})
    update.coordinator.api.query.return_value = None
    update.coordinator.api.error = "job rejected"
    with pytest.raises(HomeAssistantError) as exc_info:
        await update.async_install(version=None, backup=False)
    assert exc_info.value.translation_key == "system_update_failed"
    assert exc_info.value.translation_placeholders == {
        "host": update.coordinator.host,
        "error": "job rejected",
    }


async def test_system_update_options_updated_is_noop() -> None:
    update = _make_system_update({})
    await update.options_updated()


def test_app_update_installed_version() -> None:
    update = _make_app_update({"version": "1.2.3"})
    assert update.installed_version == "1.2.3"


def test_app_update_latest_version_no_update_available() -> None:
    update = _make_app_update({"version": "1.2.3", "update_available": False})
    assert update.latest_version == "1.2.3"


def test_app_update_latest_version_unknown_catalog_shows_image_update() -> None:
    update = _make_app_update(
        {"version": "1.2.3", "update_available": True, "latest_version": "unknown"}
    )
    assert update.latest_version == "1.2.3 (image update)"


def test_app_update_latest_version_unknown_no_installed_shows_image_update() -> None:
    update = _make_app_update({"update_available": True, "latest_version": "unknown"})
    assert update.latest_version == "image update"


def test_app_update_latest_version_same_as_installed_shows_image_update() -> None:
    update = _make_app_update(
        {"version": "1.2.3", "update_available": True, "latest_version": "1.2.3"}
    )
    assert update.latest_version == "1.2.3 (image update)"


def test_app_update_latest_version_real_catalog_version() -> None:
    update = _make_app_update(
        {"version": "1.2.3", "update_available": True, "latest_version": "1.3.0"}
    )
    assert update.latest_version == "1.3.0"


def test_app_update_title_and_in_progress() -> None:
    update = _make_app_update({"name": "Plex", "update_jobid": 42})
    assert update.title == "Plex"
    assert update.in_progress is True


async def test_app_update_async_install_not_running_logs_and_skips() -> None:
    update = _make_app_update({"id": "a1"})
    update.coordinator.data["app"] = {"a1": {"state": "STOPPED"}}
    await update.async_install(version=None, backup=False)
    update.coordinator.api.query.assert_not_awaited()


async def test_app_update_async_install_success() -> None:
    update = _make_app_update({"id": "a1"})
    update.coordinator.data["app"] = {"a1": {"state": "RUNNING"}}
    update.coordinator.api.query.return_value = 99
    await update.async_install(version=None, backup=False)
    update.coordinator.api.query.assert_awaited_once_with("app.upgrade", ["a1"])
    assert update._data["update_jobid"] == 99
    update.coordinator.async_refresh.assert_awaited_once()


async def test_app_update_async_install_failure_raises() -> None:
    update = _make_app_update({"id": "a1"})
    update.coordinator.data["app"] = {"a1": {"state": "RUNNING"}}
    update.coordinator.api.query.return_value = None
    update.coordinator.api.error = "upgrade failed"
    with pytest.raises(HomeAssistantError) as exc_info:
        await update.async_install(version=None, backup=False)
    assert exc_info.value.translation_key == "app_update_failed"
    assert exc_info.value.translation_placeholders == {
        "app": "a1",
        "host": update.coordinator.host,
        "error": "upgrade failed",
    }
