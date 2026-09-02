"""Tests for the Community store file system helpers."""

from pathlib import Path

import pytest

from homeassistant.components.store.utils.file_system import (
    async_exists,
    async_remove,
    async_remove_directory,
)
from homeassistant.core import HomeAssistant


async def test_exists(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test checking whether a path exists."""
    target = tmp_path / "target"
    assert not await async_exists(hass, target)

    target.touch()
    assert await async_exists(hass, target)


@pytest.mark.parametrize(
    "missing_ok",
    [pytest.param(False, id="not_missing_ok"), pytest.param(True, id="missing_ok")],
)
async def test_remove(hass: HomeAssistant, tmp_path: Path, missing_ok: bool) -> None:
    """Test removing a file that is there."""
    target = tmp_path / "target"
    target.touch()

    await async_remove(hass, target, missing_ok=missing_ok)

    assert not await async_exists(hass, target)


@pytest.mark.parametrize(
    "kwargs",
    [pytest.param({}, id="default"), pytest.param({"missing_ok": False}, id="strict")],
)
async def test_remove_missing_raises(
    hass: HomeAssistant, tmp_path: Path, kwargs: dict[str, bool]
) -> None:
    """Test removing a file that is not there."""
    with pytest.raises(FileNotFoundError):
        await async_remove(hass, tmp_path / "target", **kwargs)


async def test_remove_missing_allowed(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test removing a file that is not there is allowed."""
    await async_remove(hass, tmp_path / "target", missing_ok=True)


@pytest.mark.parametrize(
    "missing_ok",
    [pytest.param(False, id="not_missing_ok"), pytest.param(True, id="missing_ok")],
)
async def test_remove_directory(
    hass: HomeAssistant, tmp_path: Path, missing_ok: bool
) -> None:
    """Test removing a directory that is there."""
    target = tmp_path / "target"
    target.mkdir()

    await async_remove_directory(hass, target, missing_ok=missing_ok)

    assert not await async_exists(hass, target)


@pytest.mark.parametrize(
    "kwargs",
    [pytest.param({}, id="default"), pytest.param({"missing_ok": False}, id="strict")],
)
async def test_remove_directory_missing_raises(
    hass: HomeAssistant, tmp_path: Path, kwargs: dict[str, bool]
) -> None:
    """Test removing a directory that is not there."""
    with pytest.raises(FileNotFoundError):
        await async_remove_directory(hass, tmp_path / "target", **kwargs)


async def test_remove_directory_missing_allowed(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test removing a directory that is not there is allowed."""
    await async_remove_directory(hass, tmp_path / "target", missing_ok=True)
