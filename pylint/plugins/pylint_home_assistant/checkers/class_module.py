"""Checker for entity classes placed in the correct module."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS, Module, Platform
from pylint_home_assistant.helpers.module_info import parse_module

_BASE_ENTITY_MODULES: set[str] = {
    "BaseCoordinatorEntity",
    "CoordinatorEntity",
    "Entity",
    "EntityDescription",
    "ManualTriggerEntity",
    "RestoreEntity",
    "ToggleEntity",
    "ToggleEntityDescription",
    "TriggerBaseEntity",
}
_MODULES: dict[str, set[str]] = {
    Platform.AIR_QUALITY: {"AirQualityEntity"},
    Platform.ALARM_CONTROL_PANEL: {
        "AlarmControlPanelEntity",
        "AlarmControlPanelEntityDescription",
    },
    Platform.ASSIST_SATELLITE: {
        "AssistSatelliteEntity",
        "AssistSatelliteEntityDescription",
    },
    Platform.BINARY_SENSOR: {"BinarySensorEntity", "BinarySensorEntityDescription"},
    Platform.BUTTON: {"ButtonEntity", "ButtonEntityDescription"},
    Platform.CALENDAR: {"CalendarEntity", "CalendarEntityDescription"},
    Platform.CAMERA: {"Camera", "CameraEntityDescription"},
    Platform.CLIMATE: {"ClimateEntity", "ClimateEntityDescription"},
    Module.COORDINATOR: {"DataUpdateCoordinator"},
    Platform.CONVERSATION: {"ConversationEntity"},
    Platform.COVER: {"CoverEntity", "CoverEntityDescription"},
    Platform.DATE: {"DateEntity", "DateEntityDescription"},
    Platform.DATETIME: {"DateTimeEntity", "DateTimeEntityDescription"},
    Platform.DEVICE_TRACKER: {
        "DeviceTrackerEntity",
        "ScannerEntity",
        "ScannerEntityDescription",
        "TrackerEntity",
        "TrackerEntityDescription",
    },
    Platform.EVENT: {"EventEntity", "EventEntityDescription"},
    Platform.FAN: {"FanEntity", "FanEntityDescription"},
    Platform.GEO_LOCATION: {"GeolocationEvent"},
    Platform.HUMIDIFIER: {"HumidifierEntity", "HumidifierEntityDescription"},
    Platform.IMAGE: {"ImageEntity", "ImageEntityDescription"},
    Platform.IMAGE_PROCESSING: {
        "ImageProcessingEntity",
        "ImageProcessingFaceEntity",
        "ImageProcessingEntityDescription",
    },
    Platform.LAWN_MOWER: {"LawnMowerEntity", "LawnMowerEntityDescription"},
    Platform.LIGHT: {"LightEntity", "LightEntityDescription"},
    Platform.LOCK: {"LockEntity", "LockEntityDescription"},
    Platform.MEDIA_PLAYER: {"MediaPlayerEntity", "MediaPlayerEntityDescription"},
    Platform.NOTIFY: {"NotifyEntity", "NotifyEntityDescription"},
    Platform.NUMBER: {"NumberEntity", "NumberEntityDescription", "RestoreNumber"},
    Platform.REMOTE: {"RemoteEntity", "RemoteEntityDescription"},
    Platform.SELECT: {"SelectEntity", "SelectEntityDescription"},
    Platform.SENSOR: {"RestoreSensor", "SensorEntity", "SensorEntityDescription"},
    Platform.SIREN: {"SirenEntity", "SirenEntityDescription"},
    Platform.STT: {"SpeechToTextEntity"},
    Platform.SWITCH: {"SwitchEntity", "SwitchEntityDescription"},
    Platform.TEXT: {"TextEntity", "TextEntityDescription"},
    Platform.TIME: {"TimeEntity", "TimeEntityDescription"},
    Platform.TODO: {"TodoListEntity"},
    Platform.TTS: {"TextToSpeechEntity"},
    Platform.UPDATE: {"UpdateEntity", "UpdateEntityDescription"},
    Platform.VACUUM: {"StateVacuumEntity", "VacuumEntityDescription"},
    Platform.WAKE_WORD: {"WakeWordDetectionEntity"},
    Platform.WATER_HEATER: {"WaterHeaterEntity"},
    Platform.WEATHER: {
        "CoordinatorWeatherEntity",
        "SingleCoordinatorWeatherEntity",
        "WeatherEntity",
        "WeatherEntityDescription",
    },
}
_ENTITY_COMPONENTS: set[str] = set(ENTITY_COMPONENTS).union(
    {
        "alert",
        "automation",
        "counter",
        "input_boolean",
        "input_button",
        "input_datetime",
        "input_number",
        "input_select",
        "input_text",
        "microsoft_face",
        "person",
        "plant",
        "remember_the_milk",
        "schedule",
        "script",
        "tag",
        "timer",
    }
)


_MODULE_CLASSES = {
    class_name for classes in _MODULES.values() for class_name in classes
}


class HassEnforceClassModule(BaseChecker):
    """Checker for class in correct module."""

    name = "home_assistant_enforce_class_module"
    priority = -1
    msgs = {
        "C7411": (
            "Derived %s is recommended to be placed in the '%s' module",
            "home-assistant-enforce-class-module",
            "Used when derived class should be placed in its own module.",
        ),
    }
    options = ()

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check if derived class is placed in its own module."""
        parsed = parse_module(node.root().name)
        if parsed is None:
            return

        current_integration = parsed.domain
        current_module = parsed.module or ""

        ancestors = list(node.ancestors())

        if (
            current_module != Module.ENTITY
            and current_integration not in _ENTITY_COMPONENTS
        ):
            top_level_ancestors = list(node.ancestors(recurs=False))

            for ancestor in top_level_ancestors:
                if ancestor.name in _BASE_ENTITY_MODULES and not any(
                    parent.name in _MODULE_CLASSES for parent in ancestors
                ):
                    self.add_message(
                        "home-assistant-enforce-class-module",
                        node=node,
                        args=(ancestor.name, Module.ENTITY),
                    )
                    return

        for expected_module, classes in _MODULES.items():
            if expected_module in (current_module, current_integration):
                continue

            for ancestor in ancestors:
                if ancestor.name in classes:
                    self.add_message(
                        "home-assistant-enforce-class-module",
                        node=node,
                        args=(ancestor.name, expected_module),
                    )
                    return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceClassModule(linter))
