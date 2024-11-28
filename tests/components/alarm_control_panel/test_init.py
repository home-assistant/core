"""Test for the alarm control panel const module."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import (
    ATTR_CODE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, frame
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from . import help_async_setup_entry_init, help_async_unload_entry
from .conftest import MockAlarmControlPanel

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
    setup_test_component_platform,
)


async def help_test_async_alarm_control_panel_service(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    code: str | None | UndefinedType = UNDEFINED,
) -> None:
    """Help to lock a test lock."""
    data: dict[str, Any] = {"entity_id": entity_id}
    if code is not UNDEFINED:
        data[ATTR_CODE] = code

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, service, data, blocking=True
    )
    await hass.async_block_till_done()


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockAlarmControlPanelEntity(alarm_control_panel.AlarmControlPanelEntity):
        _attr_supported_features = 1

    entity = MockAlarmControlPanelEntity()
    assert (
        entity.supported_features
        is alarm_control_panel.AlarmControlPanelEntityFeature(1)
    )
    assert "MockAlarmControlPanelEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "AlarmControlPanelEntityFeature.ARM_HOME" in caplog.text
    caplog.clear()
    assert (
        entity.supported_features
        is alarm_control_panel.AlarmControlPanelEntityFeature(1)
    )
    assert "is using deprecated supported features values" not in caplog.text


async def test_set_mock_alarm_control_panel_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test mock attributes and default code stored in the registry."""
    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "1234"},
    )
    await hass.async_block_till_done()

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code
        == "1234"
    )
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state is not None
    assert state.attributes["code_format"] == CodeFormat.NUMBER
    assert (
        state.attributes["supported_features"]
        == AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
    )


async def test_default_code_option_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test default code stored in the registry is updated."""

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code is None
    )

    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "4321"},
    )
    await hass.async_block_till_done()

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code
        == "4321"
    )


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(CodeFormat.TEXT, AlarmControlPanelEntityFeature.ARM_AWAY)],
)
async def test_alarm_control_panel_arm_with_code(
    hass: HomeAssistant, mock_alarm_control_panel_entity: MockAlarmControlPanel
) -> None:
    """Test alarm control panel entity with open service."""
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state.attributes["code_format"] == CodeFormat.TEXT

    with pytest.raises(ServiceValidationError):
        await help_test_async_alarm_control_panel_service(
            hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_alarm_control_panel_service(
            hass,
            mock_alarm_control_panel_entity.entity_id,
            SERVICE_ALARM_ARM_AWAY,
            code="",
        )
    await help_test_async_alarm_control_panel_service(
        hass,
        mock_alarm_control_panel_entity.entity_id,
        SERVICE_ALARM_ARM_AWAY,
        code="1234",
    )
    assert mock_alarm_control_panel_entity.calls_arm_away.call_count == 1
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with("1234")


@pytest.mark.parametrize(
    ("code_format", "code_arm_required"),
    [(CodeFormat.NUMBER, False)],
)
async def test_alarm_control_panel_with_no_code(
    hass: HomeAssistant, mock_alarm_control_panel_entity: MockAlarmControlPanel
) -> None:
    """Test alarm control panel entity without code."""
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
    )
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_CUSTOM_BYPASS
    )
    mock_alarm_control_panel_entity.calls_arm_custom.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_HOME
    )
    mock_alarm_control_panel_entity.calls_arm_home.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_NIGHT
    )
    mock_alarm_control_panel_entity.calls_arm_night.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_VACATION
    )
    mock_alarm_control_panel_entity.calls_arm_vacation.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_DISARM
    )
    mock_alarm_control_panel_entity.calls_disarm.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_TRIGGER
    )
    mock_alarm_control_panel_entity.calls_trigger.assert_called_with(None)


@pytest.mark.parametrize(
    ("code_format", "code_arm_required"),
    [(CodeFormat.NUMBER, True)],
)
async def test_alarm_control_panel_with_default_code(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test alarm control panel entity without code."""
    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "1234"},
    )
    await hass.async_block_till_done()

    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
    )
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_CUSTOM_BYPASS
    )
    mock_alarm_control_panel_entity.calls_arm_custom.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_HOME
    )
    mock_alarm_control_panel_entity.calls_arm_home.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_NIGHT
    )
    mock_alarm_control_panel_entity.calls_arm_night.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_VACATION
    )
    mock_alarm_control_panel_entity.calls_arm_vacation.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_DISARM
    )
    mock_alarm_control_panel_entity.calls_disarm.assert_called_with("1234")


@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_alarm_control_panel_not_log_deprecated_state_warning(
    hass: HomeAssistant,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test correctly using alarm_state doesn't log issue or raise repair."""
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state is not None
    assert (
        "the 'alarm_state' property and return its state using the AlarmControlPanelState enum"
        not in caplog.text
    )


@pytest.mark.usefixtures("mock_as_custom_component")
@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_alarm_control_panel_log_deprecated_state_warning_using_state_prop(
    hass: HomeAssistant,
    code_format: CodeFormat | None,
    supported_features: AlarmControlPanelEntityFeature,
    code_arm_required: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test incorrectly using state property does log issue and raise repair."""

    class MockLegacyAlarmControlPanel(MockAlarmControlPanel):
        """Mocked alarm control entity."""

        def __init__(
            self,
            supported_features: AlarmControlPanelEntityFeature = AlarmControlPanelEntityFeature(
                0
            ),
            code_format: CodeFormat | None = None,
            code_arm_required: bool = True,
        ) -> None:
            """Initialize the alarm control."""
            super().__init__(supported_features, code_format, code_arm_required)

        @property
        def state(self) -> str:
            """Return the state of the entity."""
            return "disarmed"

    entity = MockLegacyAlarmControlPanel(
        supported_features=supported_features,
        code_format=code_format,
        code_arm_required=code_arm_required,
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
        built_in=False,
    )
    setup_test_component_platform(
        hass, ALARM_CONTROL_PANEL_DOMAIN, [entity], from_config_entry=True
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None

    assert (
        "Detected that custom integration 'alarm_control_panel' is setting state"
        " directly. Entity None (<class 'tests.components.alarm_control_panel."
        "test_init.test_alarm_control_panel_log_deprecated_state_warning_using"
        "_state_prop.<locals>.MockLegacyAlarmControlPanel'>) should implement"
        " the 'alarm_state' property and return its state using the AlarmControlPanelState"
        " enum at test_init.py, line 123: yield. This will stop working in Home Assistant"
        " 2025.11, please create a bug report at" in caplog.text
    )


@pytest.mark.usefixtures("mock_as_custom_component")
@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_alarm_control_panel_log_deprecated_state_warning_using_attr_state_attr(
    hass: HomeAssistant,
    code_format: CodeFormat | None,
    supported_features: AlarmControlPanelEntityFeature,
    code_arm_required: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test incorrectly using _attr_state attribute does log issue and raise repair."""

    class MockLegacyAlarmControlPanel(MockAlarmControlPanel):
        """Mocked alarm control entity."""

        def __init__(
            self,
            supported_features: AlarmControlPanelEntityFeature = AlarmControlPanelEntityFeature(
                0
            ),
            code_format: CodeFormat | None = None,
            code_arm_required: bool = True,
        ) -> None:
            """Initialize the alarm control."""
            super().__init__(supported_features, code_format, code_arm_required)

        def alarm_disarm(self, code: str | None = None) -> None:
            """Mock alarm disarm calls."""
            self._attr_state = "disarmed"

    entity = MockLegacyAlarmControlPanel(
        supported_features=supported_features,
        code_format=code_format,
        code_arm_required=code_arm_required,
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
    setup_test_component_platform(
        hass, ALARM_CONTROL_PANEL_DOMAIN, [entity], from_config_entry=True
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None

    assert (
        "Detected that custom integration 'alarm_control_panel' is setting state directly."
        not in caplog.text
    )

    await help_test_async_alarm_control_panel_service(
        hass, entity.entity_id, SERVICE_ALARM_DISARM
    )

    assert (
        "Detected that custom integration 'alarm_control_panel' is setting state directly."
        " Entity alarm_control_panel.test_alarm_control_panel"
        " (<class 'tests.components.alarm_control_panel.test_init."
        "test_alarm_control_panel_log_deprecated_state_warning_using_attr_state_attr."
        "<locals>.MockLegacyAlarmControlPanel'>) should implement the 'alarm_state' property"
        " and return its state using the AlarmControlPanelState enum at test_init.py, line 123:"
        " yield. This will stop working in Home Assistant 2025.11,"
        " please create a bug report at" in caplog.text
    )
    caplog.clear()
    await help_test_async_alarm_control_panel_service(
        hass, entity.entity_id, SERVICE_ALARM_DISARM
    )
    # Test we only log once
    assert (
        "Detected that custom integration 'alarm_control_panel' is setting state directly."
        not in caplog.text
    )


@pytest.mark.usefixtures("mock_as_custom_component")
@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_alarm_control_panel_deprecated_state_does_not_break_state(
    hass: HomeAssistant,
    code_format: CodeFormat | None,
    supported_features: AlarmControlPanelEntityFeature,
    code_arm_required: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test using _attr_state attribute does not break state."""

    class MockLegacyAlarmControlPanel(MockAlarmControlPanel):
        """Mocked alarm control entity."""

        def __init__(
            self,
            supported_features: AlarmControlPanelEntityFeature = AlarmControlPanelEntityFeature(
                0
            ),
            code_format: CodeFormat | None = None,
            code_arm_required: bool = True,
        ) -> None:
            """Initialize the alarm control."""
            self._attr_state = "armed_away"
            super().__init__(supported_features, code_format, code_arm_required)

        def alarm_disarm(self, code: str | None = None) -> None:
            """Mock alarm disarm calls."""
            self._attr_state = "disarmed"

    entity = MockLegacyAlarmControlPanel(
        supported_features=supported_features,
        code_format=code_format,
        code_arm_required=code_arm_required,
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
    setup_test_component_platform(
        hass, ALARM_CONTROL_PANEL_DOMAIN, [entity], from_config_entry=True
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "armed_away"

    await help_test_async_alarm_control_panel_service(
        hass, entity.entity_id, SERVICE_ALARM_DISARM
    )

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "disarmed"
