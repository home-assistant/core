"""Fixturs for Alarm Control Panel tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.alarm_control_panel.const import CodeFormat
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, frame
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import MockAlarm

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


@pytest.fixture
def mock_alarm_control_panel_entities() -> dict[str, MockAlarm]:
    """Mock Alarm control panel class."""
    return {
        "arm_code": MockAlarm(
            name="Alarm arm code",
            code_arm_required=True,
            unique_id="unique_arm_code",
        ),
        "no_arm_code": MockAlarm(
            name="Alarm no arm code",
            code_arm_required=False,
            unique_id="unique_no_arm_code",
        ),
    }


class MockAlarmControlPanel(AlarmControlPanelEntity):
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
        self.calls_disarm = MagicMock()
        self.calls_arm_home = MagicMock()
        self.calls_arm_away = MagicMock()
        self.calls_arm_night = MagicMock()
        self.calls_arm_vacation = MagicMock()
        self.calls_trigger = MagicMock()
        self.calls_arm_custom = MagicMock()
        self._attr_code_format = code_format
        self._attr_supported_features = supported_features
        self._attr_code_arm_required = code_arm_required
        self._attr_has_entity_name = True
        self._attr_name = "test_alarm_control_panel"
        self._attr_unique_id = "very_unique_alarm_control_panel_id"
        super().__init__()

    def alarm_disarm(self, code: str | None = None) -> None:
        """Mock alarm disarm calls."""
        self.calls_disarm(code)

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Mock arm home calls."""
        self.calls_arm_home(code)

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Mock arm away calls."""
        self.calls_arm_away(code)

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Mock arm night calls."""
        self.calls_arm_night(code)

    def alarm_arm_vacation(self, code: str | None = None) -> None:
        """Mock arm vacation calls."""
        self.calls_arm_vacation(code)

    def alarm_trigger(self, code: str | None = None) -> None:
        """Mock trigger calls."""
        self.calls_trigger(code)

    def alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Mock arm custom bypass calls."""
        self.calls_arm_custom(code)


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(name="mock_as_custom_component")
async def mock_frame(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Mock frame."""
    with patch(
        "homeassistant.helpers.frame.get_integration_frame",
        return_value=frame.IntegrationFrame(
            custom_integration=True,
            integration="alarm_control_panel",
            module="test_init.py",
            relative_filename="test_init.py",
            frame=frame.get_current_frame(),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture
async def code_format() -> CodeFormat | None:
    """Return the code format for the test alarm control panel entity."""
    return CodeFormat.NUMBER


@pytest.fixture
async def code_arm_required() -> bool:
    """Return if code required for arming."""
    return True


@pytest.fixture(name="supported_features")
async def alarm_control_panel_supported_features() -> AlarmControlPanelEntityFeature:
    """Return the supported features for the test alarm control panel entity."""
    return (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
    )


@pytest.fixture(name="mock_alarm_control_panel_entity")
async def setup_alarm_control_panel_platform_test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    code_format: CodeFormat | None,
    supported_features: AlarmControlPanelEntityFeature,
    code_arm_required: bool,
) -> MagicMock:
    """Set up alarm control panel entity using an entity platform."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [ALARM_CONTROL_PANEL_DOMAIN]
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed sensor without device class -> no name
    entity = MockAlarmControlPanel(
        supported_features=supported_features,
        code_format=code_format,
        code_arm_required=code_arm_required,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test alarm control panel platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{ALARM_CONTROL_PANEL_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None

    return entity
