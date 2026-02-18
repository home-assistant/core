"""The tests for the Vacuum entity integration."""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any

import pytest

from homeassistant.components.vacuum import (
    DOMAIN,
    SERVICE_CLEAN_AREA,
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
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import (
    MockVacuum,
    MockVacuumWithCleanArea,
    help_async_setup_entry_init,
    help_async_unload_entry,
)
from .common import async_start

from tests.common import (
    MockConfigEntry,
    MockEntity,
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


@pytest.mark.usefixtures("config_flow_fixture")
@pytest.mark.parametrize(
    ("area_mapping", "targeted_areas", "targeted_segments"),
    [
        (
            {"area_1": ["seg_1"], "area_2": ["seg_2", "seg_3"]},
            ["area_1", "area_2"],
            ["seg_1", "seg_2", "seg_3"],
        ),
        (
            {"area_1": ["seg_1", "seg_2"], "area_2": ["seg_2", "seg_3"]},
            ["area_1", "area_2"],
            ["seg_1", "seg_2", "seg_3"],
        ),
    ],
)
async def test_clean_area_service(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_mapping: dict[str, list[str]],
    targeted_areas: list[str],
    targeted_segments: list[str],
) -> None:
    """Test clean_area service calls async_clean_segments with correct segments."""
    mock_vacuum = MockVacuumWithCleanArea(name="Testing", entity_id="vacuum.testing")

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
    await hass.async_block_till_done()

    entity_registry.async_update_entity_options(
        mock_vacuum.entity_id,
        DOMAIN,
        {
            "area_mapping": area_mapping,
            "last_seen_segments": [asdict(segment) for segment in mock_vacuum.segments],
        },
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAN_AREA,
        {"entity_id": mock_vacuum.entity_id, "cleaning_area_id": targeted_areas},
        blocking=True,
    )

    assert len(mock_vacuum.clean_segments_calls) == 1
    assert mock_vacuum.clean_segments_calls[0][0] == targeted_segments


@pytest.mark.usefixtures("config_flow_fixture")
@pytest.mark.parametrize(
    ("area_mapping", "targeted_areas"),
    [
        ({}, ["area_1"]),
        ({"area_1": ["seg_1"]}, ["area_2"]),
    ],
)
async def test_clean_area_no_segments(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_mapping: dict[str, list[str]],
    targeted_areas: list[str],
) -> None:
    """Test clean_area does nothing when no segments to clean."""
    mock_vacuum = MockVacuumWithCleanArea(name="Testing", entity_id="vacuum.testing")

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
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAN_AREA,
        {"entity_id": mock_vacuum.entity_id, "cleaning_area_id": targeted_areas},
        blocking=True,
    )

    entity_registry.async_update_entity_options(
        mock_vacuum.entity_id,
        DOMAIN,
        {
            "area_mapping": area_mapping,
            "last_seen_segments": [asdict(segment) for segment in mock_vacuum.segments],
        },
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAN_AREA,
        {"entity_id": mock_vacuum.entity_id, "cleaning_area_id": targeted_areas},
        blocking=True,
    )

    assert len(mock_vacuum.clean_segments_calls) == 0


@pytest.mark.usefixtures("config_flow_fixture")
async def test_clean_area_methods_not_implemented(hass: HomeAssistant) -> None:
    """Test async_get_segments and async_clean_segments raise NotImplementedError."""

    class MockVacuumNoImpl(MockEntity, StateVacuumEntity):
        """Mock vacuum without implementations."""

        _attr_supported_features = (
            VacuumEntityFeature.STATE | VacuumEntityFeature.CLEAN_AREA
        )
        _attr_activity = VacuumActivity.DOCKED

    mock_vacuum = MockVacuumNoImpl(name="Testing", entity_id="vacuum.testing")

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
    await hass.async_block_till_done()

    with pytest.raises(NotImplementedError):
        await mock_vacuum.async_get_segments()

    with pytest.raises(NotImplementedError):
        await mock_vacuum.async_clean_segments(["seg_1"])


async def test_clean_area_no_registry_entry() -> None:
    """Test error handling when registry entry is not set."""
    mock_vacuum = MockVacuumWithCleanArea(name="Testing", entity_id="vacuum.testing")

    with pytest.raises(
        RuntimeError,
        match="Cannot access last_seen_segments, registry entry is not set",
    ):
        mock_vacuum.last_seen_segments  # noqa: B018

    with pytest.raises(
        RuntimeError,
        match="Cannot perform area clean, registry entry is not set",
    ):
        await mock_vacuum.async_internal_clean_area(["area_1"])

    with pytest.raises(
        RuntimeError,
        match="Cannot create segments issue, registry entry is not set",
    ):
        mock_vacuum.async_create_segments_issue()


@pytest.mark.usefixtures("config_flow_fixture")
async def test_last_seen_segments(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test last_seen_segments property."""
    mock_vacuum = MockVacuumWithCleanArea(name="Testing", entity_id="vacuum.testing")

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
    await hass.async_block_till_done()

    assert mock_vacuum.last_seen_segments is None

    entity_registry.async_update_entity_options(
        mock_vacuum.entity_id,
        DOMAIN,
        {
            "area_mapping": {},
            "last_seen_segments": [asdict(segment) for segment in mock_vacuum.segments],
        },
    )

    assert mock_vacuum.last_seen_segments == mock_vacuum.segments


@pytest.mark.usefixtures("config_flow_fixture")
async def test_last_seen_segments_and_issue_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test last_seen_segments property and segments issue creation."""
    mock_vacuum = MockVacuumWithCleanArea(name="Testing", entity_id="vacuum.testing")

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
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(mock_vacuum.entity_id)
    mock_vacuum.async_create_segments_issue()

    issue_id = f"segments_changed_{entity_entry.id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "segments_changed"


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
