"""The tests for the Vacuum entity integration."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from homeassistant.components.vacuum import (
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant

from . import MockVacuum, help_async_setup_entry_init, help_async_unload_entry
from .common import async_start

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
    setup_test_component_platform,
)


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_CLEAN_SPOT, VacuumActivity.CLEANING),
        (SERVICE_PAUSE, VacuumActivity.PAUSED),
        (SERVICE_RETURN_TO_BASE, VacuumActivity.RETURNING),
        (SERVICE_START, VacuumActivity.CLEANING),
        (SERVICE_STOP, VacuumActivity.IDLE),
    ],
)
async def test_state_services(
    hass: HomeAssistant, config_flow_fixture: None, service: str, expected_state: str
) -> None:
    """Test get vacuum service that affect state."""
    mock_vacuum = MockVacuum(
        name="Testing",
        entity_id="vacuum.testing",
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [mock_vacuum], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": mock_vacuum.entity_id},
        blocking=True,
    )
    activity = hass.states.get(mock_vacuum.entity_id)

    assert activity.state == expected_state


async def test_fan_speed(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test set vacuum fan speed."""
    mock_vacuum = MockVacuum(
        name="Testing",
        entity_id="vacuum.testing",
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [mock_vacuum], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {"entity_id": mock_vacuum.entity_id, "fan_speed": "high"},
        blocking=True,
    )

    assert mock_vacuum.fan_speed == "high"


async def test_locate(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test vacuum locate."""

    calls = []

    class MockVacuumWithLocation(MockVacuum):
        def __init__(self, calls: list[str], **kwargs) -> None:
            super().__init__()
            self._attr_supported_features = (
                self.supported_features | VacuumEntityFeature.LOCATE
            )
            self._calls = calls

        def locate(self, **kwargs: Any) -> None:
            self._calls.append("locate")

    mock_vacuum = MockVacuumWithLocation(
        name="Testing", entity_id="vacuum.testing", calls=calls
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [mock_vacuum], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOCATE,
        {"entity_id": mock_vacuum.entity_id},
        blocking=True,
    )

    assert "locate" in calls


async def test_send_command(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test Vacuum send command."""

    strings = []

    class MockVacuumWithSendCommand(MockVacuum):
        def __init__(self, strings: list[str], **kwargs) -> None:
            super().__init__()
            self._attr_supported_features = (
                self.supported_features | VacuumEntityFeature.SEND_COMMAND
            )
            self._strings = strings

        def send_command(
            self,
            command: str,
            params: dict[str, Any] | list[Any] | None = None,
            **kwargs: Any,
        ) -> None:
            if command == "add_str":
                self._strings.append(params["str"])

    mock_vacuum = MockVacuumWithSendCommand(
        name="Testing", entity_id="vacuum.testing", strings=strings
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [mock_vacuum], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            "entity_id": mock_vacuum.entity_id,
            "command": "add_str",
            "params": {"str": "test"},
        },
        blocking=True,
    )

    assert "test" in strings


@pytest.mark.parametrize(("is_built_in", "log_warnings"), [(True, 0), (False, 3)])
async def test_vacuum_log_deprecated_battery_using_properties(
    hass: HomeAssistant,
    config_flow_fixture: None,
    caplog: pytest.LogCaptureFixture,
    is_built_in: bool,
    log_warnings: int,
) -> None:
    """Test incorrectly using battery properties logs warning."""

    class MockLegacyVacuum(MockVacuum):
        """Mocked vacuum entity."""

        @property
        def activity(self) -> VacuumActivity:
            """Return the state of the entity."""
            return VacuumActivity.CLEANING

        @property
        def battery_level(self) -> int:
            """Return the battery level of the vacuum."""
            return 50

        @property
        def battery_icon(self) -> str:
            """Return the battery icon of the vacuum."""
            return "mdi:battery-50"

    entity = MockLegacyVacuum(
        name="Testing",
        entity_id="vacuum.test",
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
        built_in=is_built_in,
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None

    assert (
        len([record for record in caplog.records if record.levelno >= logging.WARNING])
        == log_warnings
    )

    assert (
        "integration 'test' is setting the battery_icon which has been deprecated."
        in caplog.text
    ) != is_built_in
    assert (
        "integration 'test' is setting the battery_level which has been deprecated."
        in caplog.text
    ) != is_built_in


@pytest.mark.parametrize(("is_built_in", "log_warnings"), [(True, 0), (False, 3)])
async def test_vacuum_log_deprecated_battery_using_attr(
    hass: HomeAssistant,
    config_flow_fixture: None,
    caplog: pytest.LogCaptureFixture,
    is_built_in: bool,
    log_warnings: int,
) -> None:
    """Test incorrectly using _attr_battery_* attribute does log issue and raise repair."""

    class MockLegacyVacuum(MockVacuum):
        """Mocked vacuum entity."""

        def start(self) -> None:
            """Start cleaning."""
            self._attr_battery_level = 50
            self._attr_battery_icon = "mdi:battery-50"

    entity = MockLegacyVacuum(
        name="Testing",
        entity_id="vacuum.test",
    )
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
        built_in=is_built_in,
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None
    entity.start()

    assert (
        len([record for record in caplog.records if record.levelno >= logging.WARNING])
        == log_warnings
    )

    assert (
        "integration 'test' is setting the battery_level which has been deprecated."
        in caplog.text
    ) != is_built_in
    assert (
        "integration 'test' is setting the battery_icon which has been deprecated."
        in caplog.text
    ) != is_built_in

    await async_start(hass, entity.entity_id)

    caplog.clear()

    await async_start(hass, entity.entity_id)

    # Test we only log once
    assert (
        len([record for record in caplog.records if record.levelno >= logging.WARNING])
        == 0
    )


@pytest.mark.parametrize(("is_built_in", "log_warnings"), [(True, 0), (False, 1)])
async def test_vacuum_log_deprecated_battery_supported_feature(
    hass: HomeAssistant,
    config_flow_fixture: None,
    caplog: pytest.LogCaptureFixture,
    is_built_in: bool,
    log_warnings: int,
) -> None:
    """Test incorrectly setting battery supported feature logs warning."""

    class MockVacuum(StateVacuumEntity):
        """Mock vacuum class."""

        _attr_supported_features = (
            VacuumEntityFeature.STATE | VacuumEntityFeature.BATTERY
        )
        _attr_name = "Testing"

    entity = MockVacuum()
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
        built_in=is_built_in,
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None

    assert (
        len([record for record in caplog.records if record.levelno >= logging.WARNING])
        == log_warnings
    )

    assert (
        "integration 'test' is setting the battery supported feature" in caplog.text
    ) != is_built_in


async def test_vacuum_not_log_deprecated_battery_properties_during_init(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test not logging deprecation until after added to hass."""

    class MockLegacyVacuum(MockVacuum):
        """Mocked vacuum entity."""

        def __init__(self, **kwargs: Any) -> None:
            """Initialize a mock vacuum entity."""
            super().__init__(**kwargs)
            self._attr_battery_level = 50

        @property
        def activity(self) -> VacuumActivity:
            """Return the state of the entity."""
            return VacuumActivity.CLEANING

    entity = MockLegacyVacuum(
        name="Testing",
        entity_id="vacuum.test",
    )
    assert entity.battery_level == 50

    assert (
        len([record for record in caplog.records if record.levelno >= logging.WARNING])
        == 0
    )
