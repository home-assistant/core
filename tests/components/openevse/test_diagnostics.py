"""Test OpenEVSE diagnostics."""

from datetime import datetime
from enum import Enum
from typing import Any
from unittest.mock import MagicMock

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
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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
    await hass.config_entries.async_setup(entry.entry_id)
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
            # Copy other properties so that inspect.getattr_static finds them in __dict__
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
        def ota_update(self) -> tuple[str, ...]:
            return ("v1.0", "v2.0")

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
        def wifi_firmware(self) -> Any:
            return lambda: "callable_value"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Inject the FakeCharger into the coordinator to isolate side effects
    coordinator = mock_config_entry.runtime_data
    coordinator.charger = FakeCharger(mock_charger)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # status should be omitted due to AttributeError
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

    # ota_update should be coerced to list
    assert diagnostics["charger"]["ota_update"] == ["v1.0", "v2.0"]

    # service_level should have keys coerced to str
    assert diagnostics["charger"]["service_level"] == {"MockEnum.TEST": "level_2"}

    # uptime should fallback to string representation
    assert diagnostics["charger"]["uptime"] == "custom_str"

    # wifi_firmware should be omitted because it is callable
    assert "wifi_firmware" not in diagnostics["charger"]
