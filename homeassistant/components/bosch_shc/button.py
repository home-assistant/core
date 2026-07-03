"""Platform for button integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from boschshcpy.device import SHCDevice
from boschshcpy.scenario import SHCScenario
from boschshcpy.services_impl import DetectionTestService, WalkTestService

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCButtonEntityDescription(ButtonEntityDescription):
    """Describes a SHC device-backed button."""

    press_fn: Callable[[SHCDevice], None]


IMPULSE_RELAY_BUTTON = "impulse"
SMOKE_TEST_BUTTON = "smoke_test"
WALK_TEST_BUTTON = "walk_test"
WALK_TEST_STOP_BUTTON = "walk_test_stop"
DETECTION_TEST_BUTTON = "detection_test"
DETECTION_TEST_STOP_BUTTON = "detection_test_stop"
TAMPER_RESET_BUTTON = "reset_tamper"

BUTTON_DESCRIPTIONS: dict[str, SHCButtonEntityDescription] = {
    IMPULSE_RELAY_BUTTON: SHCButtonEntityDescription(
        key=IMPULSE_RELAY_BUTTON,
        translation_key=IMPULSE_RELAY_BUTTON,
        press_fn=lambda device: device.trigger_impulse_state(),
    ),
    SMOKE_TEST_BUTTON: SHCButtonEntityDescription(
        key=SMOKE_TEST_BUTTON,
        translation_key=SMOKE_TEST_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.smoketest_requested(),
    ),
    WALK_TEST_BUTTON: SHCButtonEntityDescription(
        key=WALK_TEST_BUTTON,
        translation_key=WALK_TEST_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.set_walk_state_request(
            WalkTestService.WalkStateRequest.WALK_STATE_START
        ),
    ),
    WALK_TEST_STOP_BUTTON: SHCButtonEntityDescription(
        key=WALK_TEST_STOP_BUTTON,
        translation_key=WALK_TEST_STOP_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.set_walk_state_request(
            WalkTestService.WalkStateRequest.WALK_STATE_STOP
        ),
    ),
    DETECTION_TEST_BUTTON: SHCButtonEntityDescription(
        key=DETECTION_TEST_BUTTON,
        translation_key=DETECTION_TEST_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.set_detection_state_request(
            DetectionTestService.DetectionStateRequest.DETECTION_STATE_START
        ),
    ),
    DETECTION_TEST_STOP_BUTTON: SHCButtonEntityDescription(
        key=DETECTION_TEST_STOP_BUTTON,
        translation_key=DETECTION_TEST_STOP_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.set_detection_state_request(
            DetectionTestService.DetectionStateRequest.DETECTION_STATE_STOP
        ),
    ),
    TAMPER_RESET_BUTTON: SHCButtonEntityDescription(
        key=TAMPER_RESET_BUTTON,
        translation_key=TAMPER_RESET_BUTTON,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.reset_tampered_state(),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC button platform."""
    session = config_entry.runtime_data
    shc_uid = session.information.unique_id

    def _make(device: SHCDevice, button_type: str) -> SHCButton:
        return SHCButton(
            device=device,
            entity_description=BUTTON_DESCRIPTIONS[button_type],
            parent_id=shc_uid,
            entry_id=config_entry.entry_id,
        )

    entities: list[ButtonEntity] = [
        SHCScenarioButton(
            scenario=scenario,
            shc_uid=shc_uid,
        )
        for scenario in session.scenarios
    ]

    entities.extend(
        _make(device, IMPULSE_RELAY_BUTTON)
        for device in session.device_helper.micromodule_impulse_relays
    )

    entities.extend(
        _make(device, SMOKE_TEST_BUTTON)
        for device in (
            *session.device_helper.smoke_detectors,
            *session.device_helper.twinguards,
        )
    )

    for device in session.device_helper.motion_detectors2:
        if device.supports_walk_test and device.walk_state is not None:
            entities.append(_make(device, WALK_TEST_BUTTON))
            entities.append(_make(device, WALK_TEST_STOP_BUTTON))
        if device.supports_detection_test:
            entities.append(_make(device, DETECTION_TEST_BUTTON))
            entities.append(_make(device, DETECTION_TEST_STOP_BUTTON))
        entities.append(_make(device, TAMPER_RESET_BUTTON))

    async_add_entities(entities)


class SHCScenarioButton(ButtonEntity):
    """Button entity that triggers a Bosch SHC scenario (not an SHCDevice, so no SHCEntity)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:script-text-play"

    def __init__(
        self,
        scenario: SHCScenario,
        shc_uid: str,
    ) -> None:
        """Initialize a scenario button."""
        self._scenario = scenario
        self._attr_unique_id = f"{shc_uid}_scenario_{scenario.id}"
        self._attr_name = scenario.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, shc_uid)},
        )

    @override
    def press(self) -> None:
        """Trigger the scenario."""
        self._scenario.trigger()


class SHCButton(SHCEntity, ButtonEntity):
    """Representation of a SHC device-backed button."""

    entity_description: SHCButtonEntityDescription

    def __init__(
        self,
        device: SHCDevice,
        entity_description: SHCButtonEntityDescription,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_{entity_description.key}"

    @override
    def press(self) -> None:
        """Press the button."""
        self.entity_description.press_fn(self._device)
