"""Tests for instance ID helper."""
from json import JSONDecodeError
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id


async def test_get_id_empty(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Get unique ID."""
    uuid = await instance_id.async_get(hass)
    assert uuid is not None
    # Assert it's stored
    assert hass_storage["core.uuid"]["data"]["uuid"] == uuid


async def test_get_id_load_fail(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Migrate existing file with error."""
    hass_storage["core.uuid"] = None  # Invalid, will make store.async_load raise

    uuid = await instance_id.async_get(hass)

    assert uuid is not None

    # Assert it's stored
    assert hass_storage["core.uuid"]["data"]["uuid"] == uuid

    assert (
        "Could not read hass instance ID from 'core.uuid' or '.uuid', a "
        "new instance ID will be generated" in caplog.text
    )


async def test_get_id_migrate(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Migrate existing file."""
    with patch(
        "homeassistant.util.json.load_json", return_value={"uuid": "1234"}
    ), patch("os.path.isfile", return_value=True), patch("os.remove") as mock_remove:
        uuid = await instance_id.async_get(hass)

    assert uuid == "1234"

    # Assert it's stored
    assert hass_storage["core.uuid"]["data"]["uuid"] == uuid

    # assert old deleted
    assert len(mock_remove.mock_calls) == 1


async def test_get_id_migrate_fail(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Migrate existing file with error."""
    with patch(
        "homeassistant.util.json.load_json",
        side_effect=JSONDecodeError("test_error", "test", 1),
    ), patch("os.path.isfile", return_value=True), patch("os.remove") as mock_remove:
        uuid = await instance_id.async_get(hass)

    assert uuid is not None

    # Assert it's stored
    assert hass_storage["core.uuid"]["data"]["uuid"] == uuid

    # assert old not deleted
    assert len(mock_remove.mock_calls) == 0

    assert (
        "Could not read hass instance ID from 'core.uuid' or '.uuid', a "
        "new instance ID will be generated" in caplog.text
    )
