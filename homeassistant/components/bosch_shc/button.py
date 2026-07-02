"""Platform for button integration."""

from typing import override

from boschshcpy import SHCSmokeDetector, SHCTwinguard
from boschshcpy.device import SHCDevice
from boschshcpy.models_impl import SHCMicromoduleRelay, SHCMotionDetector2
from boschshcpy.scenario import SHCScenario
from boschshcpy.services_impl import DetectionTestService, WalkTestService

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC button platform."""
    session = config_entry.runtime_data
    shc_uid = session.information.unique_id

    entities: list[ButtonEntity] = [
        SHCScenarioButton(
            scenario=scenario,
            shc_uid=shc_uid,
            entry_id=config_entry.entry_id,
        )
        for scenario in session.scenarios
    ]

    entities.extend(
        SHCImpulseRelayButton(
            device=device,
            parent_id=shc_uid,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.micromodule_impulse_relays
    )

    entities.extend(
        SHCSmokeTestButton(
            device=device,
            parent_id=shc_uid,
            entry_id=config_entry.entry_id,
        )
        for device in (
            *session.device_helper.smoke_detectors,
            *session.device_helper.twinguards,
        )
    )

    for device in session.device_helper.motion_detectors2:
        if device.supports_walk_test and device.walk_state is not None:
            entities.append(
                SHCWalkTestButton(
                    device=device,
                    parent_id=shc_uid,
                    entry_id=config_entry.entry_id,
                )
            )
            entities.append(
                SHCWalkTestStopButton(
                    device=device,
                    parent_id=shc_uid,
                    entry_id=config_entry.entry_id,
                )
            )
        if device.supports_detection_test:
            entities.append(
                SHCDetectionTestButton(
                    device=device,
                    parent_id=shc_uid,
                    entry_id=config_entry.entry_id,
                )
            )
            entities.append(
                SHCDetectionTestStopButton(
                    device=device,
                    parent_id=shc_uid,
                    entry_id=config_entry.entry_id,
                )
            )
        entities.append(
            SHCTamperResetButton(
                device=device,
                parent_id=shc_uid,
                entry_id=config_entry.entry_id,
            )
        )

    async_add_entities(entities)


class SHCScenarioButton(ButtonEntity):
    """Button entity that triggers a Bosch SHC scenario.

    Scenarios are not SHC devices, so this does not inherit SHCEntity.
    The unique_id is scoped to the controller serial so that each SHC
    controller gets its own set of scenario buttons.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:script-text-play"
    _attr_should_poll = False

    def __init__(
        self,
        scenario: SHCScenario,
        shc_uid: str,
        entry_id: str,
    ) -> None:
        """Initialize a scenario button."""
        self._scenario = scenario
        self._entry_id = entry_id
        self._attr_unique_id = f"{shc_uid}_scenario_{scenario.id}"
        self._attr_name = scenario.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, shc_uid)},
        )

    @override
    async def async_press(self) -> None:
        """Trigger the scenario."""
        await self.hass.async_add_executor_job(self._scenario.trigger)


class SHCImpulseRelayButton(SHCEntity, ButtonEntity):
    """Button entity that fires a momentary impulse on a relay module."""

    _attr_translation_key = "impulse"

    def __init__(
        self,
        device: SHCMicromoduleRelay,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the impulse relay button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_impulse"

    @override
    async def async_press(self) -> None:
        """Trigger the impulse relay."""
        await self.hass.async_add_executor_job(self._device.trigger_impulse_state)


class SHCSmokeTestButton(SHCEntity, ButtonEntity):
    """Button entity that requests a smoke detector self-test."""

    _attr_icon = "mdi:smoke-detector-alert"
    _attr_translation_key = "smoke_test"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCSmokeDetector | SHCTwinguard,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the smoke-test button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smoke_test"

    @override
    async def async_press(self) -> None:
        """Request a smoke-detector self-test."""
        await self.hass.async_add_executor_job(self._device.smoketest_requested)


class SHCWalkTestButton(SHCEntity, ButtonEntity):
    """Button that starts a walk-test on a Motion Detector II."""

    _attr_icon = "mdi:walk"
    _attr_translation_key = "walk_test"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the walk-test start button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_walk_test"

    @override
    async def async_press(self) -> None:
        """Start the walk test."""
        await self.hass.async_add_executor_job(
            self._device.set_walk_state_request,
            WalkTestService.WalkStateRequest.WALK_STATE_START,
        )


class SHCWalkTestStopButton(SHCEntity, ButtonEntity):
    """Button that stops an in-progress walk-test on a Motion Detector II."""

    _attr_icon = "mdi:stop"
    _attr_translation_key = "walk_test_stop"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the walk-test stop button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_walk_test_stop"

    @override
    async def async_press(self) -> None:
        """Stop the walk test."""
        await self.hass.async_add_executor_job(
            self._device.set_walk_state_request,
            WalkTestService.WalkStateRequest.WALK_STATE_STOP,
        )


class SHCDetectionTestButton(SHCEntity, ButtonEntity):
    """Button that starts a detection test via the DetectionTest service."""

    _attr_icon = "mdi:walk"
    _attr_translation_key = "detection_test"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the detection-test start button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_detection_test"

    @override
    async def async_press(self) -> None:
        """Start the detection test."""
        await self.hass.async_add_executor_job(
            self._device.set_detection_state_request,
            DetectionTestService.DetectionStateRequest.DETECTION_STATE_START,
        )


class SHCDetectionTestStopButton(SHCEntity, ButtonEntity):
    """Button that stops an in-progress detection test."""

    _attr_icon = "mdi:stop"
    _attr_translation_key = "detection_test_stop"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the detection-test stop button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_detection_test_stop"

    @override
    async def async_press(self) -> None:
        """Stop the detection test."""
        await self.hass.async_add_executor_job(
            self._device.set_detection_state_request,
            DetectionTestService.DetectionStateRequest.DETECTION_STATE_STOP,
        )


class SHCTamperResetButton(SHCEntity, ButtonEntity):
    """Button that resets an active tamper condition on a Motion Detector II."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_translation_key = "reset_tamper"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the tamper-reset button."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_reset_tamper"

    @override
    async def async_press(self) -> None:
        """Reset the active tamper condition."""
        await self.hass.async_add_executor_job(self._device.reset_tampered_state)
