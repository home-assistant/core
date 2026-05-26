"""Test OpenEVSE diagnostics."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.openevse.diagnostics import (
    MAX_JSON_DEPTH,
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics and redacted data."""
    entry = MockConfigEntry(
        title="openevse_mock_config",
        domain="openevse",
        data={
            "host": "192.168.1.100",
            "username": "my_username",
            "password": "my_password",
        },
        entry_id="FAKE_AUTH",
        unique_id="deadbeeffeed",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["config_entry"]["data"] == {
        "host": "192.168.1.100",
        "username": "**REDACTED**",
        "password": "**REDACTED**",
    }
    assert diagnostics["charger"]["status"] == "Charging"
    assert diagnostics["charger"]["charging_voltage"] == 240
    assert diagnostics["charger"]["charging_current"] == 32000.0


async def test_entry_diagnostics_exceptions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics handles exceptions and JSON coercion correctly."""

    class MockEnum(Enum):
        TEST = "test_value"

    class CustomObj:
        def __str__(self) -> str:
            return "custom_str"

    class CustomKeyObj:
        pass

    custom_key_obj = CustomKeyObj()

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Configure the mock_charger after setup to isolate side effects
    mock_charger.vehicle_eta = datetime(2000, 1, 1, 12, 0, 0)
    mock_charger.mode = MockEnum.TEST
    mock_charger.divertmode = {"solar", "eco"}
    mock_charger.manual_override = frozenset({"override"})
    mock_charger.ota_update = ("v1.0", lambda: "nested_callable")
    mock_charger.service_level = {MockEnum.TEST: "level_2"}
    mock_charger.uptime = CustomObj()
    mock_charger.wifi_firmware = lambda: "callable_value"

    # Set up cyclic list
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    mock_charger.openevse_firmware = cyclic

    # Set up deeply nested list
    nested: list[Any] = []
    curr = nested
    for _ in range(MAX_JSON_DEPTH + 2):
        new_list: list[Any] = []
        curr.append(new_list)
        curr = new_list
    mock_charger.wifi_signal = nested

    # Set up freeram dict
    mock_charger.freeram = {
        "simple": "val",
        123: "int_key",
        MockEnum.TEST: "enum_key",
        custom_key_obj: "obj_key",
    }

    # Patch charging_voltage to raise ValueError and status to raise AttributeError
    with (
        patch.object(
            type(mock_charger),
            "charging_voltage",
            PropertyMock(side_effect=ValueError("Connection error")),
            create=True,
        ),
        patch.object(
            type(mock_charger),
            "status",
            PropertyMock(side_effect=AttributeError("Attribute not found")),
            create=True,
        ),
    ):
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        )

    # status should be omitted because the attribute is not present
    assert "status" not in diagnostics["charger"]

    # charging_voltage should show the recorded error type only
    assert diagnostics["charger"]["charging_voltage"] == "Error: ValueError"

    # vehicle_eta should be coerced to ISO format string
    assert diagnostics["charger"]["vehicle_eta"] == "2000-01-01T12:00:00"

    # mode should be coerced to Enum raw value
    assert diagnostics["charger"]["mode"] == "test_value"

    # divertmode should be sorted and coerced to list
    assert diagnostics["charger"]["divertmode"] == ["eco", "solar"]

    # manual_override should be sorted and coerced to list
    assert diagnostics["charger"]["manual_override"] == ["override"]

    # ota_update should be coerced to list, with callable elements coerced to None
    assert diagnostics["charger"]["ota_update"] == ["v1.0", None]

    # service_level should have keys coerced to str
    assert diagnostics["charger"]["service_level"] == {"MockEnum.TEST": "level_2"}

    # uptime should fallback to type name representation
    assert diagnostics["charger"]["uptime"] == "<CustomObj object>"

    # wifi_firmware should be omitted because it is callable
    assert "wifi_firmware" not in diagnostics["charger"]

    # wifi_signal has a deeply nested list exceeding the limit
    expected_wifi_signal: list[Any] = []
    curr = expected_wifi_signal
    for _ in range(MAX_JSON_DEPTH - 1):
        new_list = []
        curr.append(new_list)
        curr = new_list
    curr.append("<Depth limit exceeded: list>")
    assert diagnostics["charger"]["wifi_signal"] == expected_wifi_signal

    # freeram key types and deterministic serialization
    assert diagnostics["charger"]["freeram"] == {
        "<int: 123>": "int_key",
        "MockEnum.TEST": "enum_key",
        "<CustomKeyObj>": "obj_key",
        "simple": "val",
    }

    # openevse_firmware contains circular reference
    assert diagnostics["charger"]["openevse_firmware"] == [
        "<Circular reference detected: list>"
    ]


async def test_entry_diagnostics_cancelled_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics handles asyncio.CancelledError correctly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Raise CancelledError on status access using patch.object
    with (
        patch.object(
            type(mock_charger),
            "status",
            PropertyMock(side_effect=asyncio.CancelledError()),
            create=True,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_get_config_entry_diagnostics(hass, mock_config_entry)
