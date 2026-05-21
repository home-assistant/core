"""Test OpenEVSE diagnostics."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any
from unittest.mock import MagicMock

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
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["config_entry"]["data"] == {
        "host": "192.168.1.100",
    }
    assert diagnostics["charger"]["status"] == "Charging"
    assert diagnostics["charger"]["charging_voltage"] == 240
    assert diagnostics["charger"]["charging_current"] == 32000.0


async def test_entry_diagnostics_redact(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics with auth data redacted."""
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


async def test_entry_diagnostics_exceptions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics handles exceptions and JSON coercion correctly."""

    class MockEnum(Enum):
        TEST = "test_value"

    class FakeCharger:
        """Fake charger to raise exceptions and return custom values for properties."""

        def __init__(self, original_charger: MagicMock) -> None:
            self._original_charger = original_charger
            # Copy other properties from the original mock for realism
            excluded = {
                "status",
                "charging_voltage",
                "vehicle_eta",
                "mode",
                "divertmode",
                "manual_override",
                "ota_update",
                "service_level",
                "uptime",
                "wifi_firmware",
                "openevse_firmware",
                "wifi_signal",
                "freeram",
            }
            # Copy all mock attributes except the overridden ones
            for key, val in original_charger.__dict__.items():
                if key not in excluded:
                    self.__dict__[key] = val

        @property
        def charging_voltage(self) -> int:
            raise ValueError("Connection error")

        @property
        def vehicle_eta(self) -> datetime:
            return datetime(2000, 1, 1, 12, 0, 0)

        @property
        def mode(self) -> MockEnum:
            return MockEnum.TEST

        @property
        def divertmode(self) -> set[str]:
            return {"solar", "eco"}

        @property
        def manual_override(self) -> frozenset[str]:
            return frozenset({"override"})

        @property
        def ota_update(self) -> tuple[Any, ...]:
            return ("v1.0", lambda: "nested_callable")

        @property
        def service_level(self) -> dict[MockEnum, str]:
            return {MockEnum.TEST: "level_2"}

        @property
        def uptime(self) -> object:
            class CustomObj:
                def __str__(self) -> str:
                    return "custom_str"

            return CustomObj()

        @property
        def custom_key_obj(self) -> object:
            class CustomKeyObj:
                pass

            return CustomKeyObj()

        @property
        def wifi_firmware(self) -> Any:
            return lambda: "callable_value"

        @property
        def openevse_firmware(self) -> list[Any]:
            cyclic: list[Any] = []
            cyclic.append(cyclic)
            return cyclic

        @property
        def wifi_signal(self) -> list[Any]:
            nested: list[Any] = []
            curr = nested
            for _ in range(MAX_JSON_DEPTH + 2):
                new_list: list[Any] = []
                curr.append(new_list)
                curr = new_list
            return nested

        @property
        def freeram(self) -> dict[Any, Any]:
            return {
                "simple": "val",
                123: "int_key",
                MockEnum.TEST: "enum_key",
                self.custom_key_obj: "obj_key",
            }

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Inject the FakeCharger into the coordinator to isolate side effects
    coordinator = mock_config_entry.runtime_data
    coordinator.charger = FakeCharger(mock_charger)

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

    class CancelledFakeCharger:
        @property
        def status(self) -> str:
            raise asyncio.CancelledError

        @property
        def websocket(self) -> Any:
            return None

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.charger = CancelledFakeCharger()

    with pytest.raises(asyncio.CancelledError):
        await async_get_config_entry_diagnostics(hass, mock_config_entry)
