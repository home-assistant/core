"""Tests for hassfest translations."""

import pytest
import voluptuous as vol

from script.hassfest import translations
from script.hassfest.model import Config

from . import get_integration


def test_string_with_no_placeholders_in_single_quotes() -> None:
    """Test string with no placeholders in single quotes."""
    schema = vol.Schema(translations.string_no_single_quoted_placeholders)

    with pytest.raises(vol.Invalid):
        schema("This has '{placeholder}' in single quotes")

    for value in (
        'This has "{placeholder}" in double quotes',
        "Simple {placeholder}",
        "No placeholder",
    ):
        schema(value)


SAMPLE_STRINGS = {
    "title": "Test Integration",
    "config": {
        "flow_title": "Configure {name}",
        "step": {
            "user": {
                "title": "Set up Test Integration",
                "description": "Enter your credentials for {name}",
                "data": {
                    "host": "Host",
                    "username": "Username",
                    "password": "Password",
                },
                "data_description": {
                    "host": "The hostname or IP address of your device",
                    "password": "The password for authentication",
                },
                "menu_options": {
                    "option_one": "First option",
                    "option_two": "Second option",
                },
                "menu_option_descriptions": {
                    "option_one": "Description of first option",
                    "option_two": "Description of second option",
                },
                "submit": "Connect",
                "sections": {
                    "advanced": {
                        "name": "Advanced settings",
                        "description": "Configure advanced options",
                        "data": {
                            "timeout": "Timeout",
                        },
                        "data_description": {
                            "timeout": "Connection timeout in seconds",
                        },
                    },
                },
            },
            "reauth_confirm": {
                "title": "Reauthenticate",
                "description": "Please reauthenticate with {name}",
                "data": {
                    "password": "Password",
                },
            },
        },
        "error": {
            "cannot_connect": "Failed to connect",
            "invalid_auth": "Invalid authentication",
            "unknown": "Unexpected error",
        },
        "abort": {
            "already_configured": "Device is already configured",
            "reauth_successful": "Reauthentication successful",
        },
        "progress": {
            "discovery": "Discovering devices",
        },
        "create_entry": {
            "default": "Successfully configured {name}",
        },
    },
    "config_subentries": {
        "device": {
            "entry_type": "Device",
            "initiate_flow": {
                "user": "Add device",
                "discovery": "Add discovered device",
            },
            "step": {
                "user": {
                    "title": "Add device",
                    "description": "Enter device details",
                    "data": {
                        "device_id": "Device ID",
                    },
                },
            },
            "error": {
                "invalid_device": "Invalid device",
            },
            "abort": {
                "device_exists": "Device already exists",
            },
        },
    },
    "options": {
        "step": {
            "init": {
                "title": "Options",
                "description": "Configure options for {name}",
                "data": {
                    "scan_interval": "Scan interval",
                },
                "data_description": {
                    "scan_interval": "How often to poll the device",
                },
            },
        },
        "error": {
            "invalid_interval": "Invalid scan interval",
        },
        "abort": {
            "cannot_connect": "Cannot connect to device",
        },
    },
    "preview_features": {
        "new_feature": {
            "name": "New feature",
            "description": "This is a new experimental feature, see https://example.com",
            "enable_confirmation": "Are you sure you want to enable this feature?",
            "disable_confirmation": "Are you sure you want to disable this feature?",
        },
    },
    "selector": {
        "mode": {
            "options": {
                "auto": "Automatic",
                "manual": "Manual",
                "eco": "Eco mode",
            },
        },
        "speed": {
            "choices": {
                "low": "Low",
                "medium": "Medium",
                "high": "High",
            },
        },
        "temperature": {
            "unit_of_measurement": {
                "celsius": "Celsius",
                "fahrenheit": "Fahrenheit",
            },
        },
        "field_new": {
            "fields": {
                "field_one": {
                    "name": "Field one",
                    "description": "Description of field one",
                },
            },
        },
        "field_old": {
            "fields": {
                "field_old": "Description of field old",
            },
        },
        "_": {
            "options": {
                "default_option": "Default option",
            },
        },
    },
    "device_automation": {
        "action_type": {
            "turn_on": "Turn on {entity_name}",
            "turn_off": "Turn off {entity_name}",
        },
        "condition_type": {
            "is_on": "{entity_name} is on",
            "is_off": "{entity_name} is off",
        },
        "trigger_type": {
            "turned_on": "{entity_name} turned on",
            "turned_off": "{entity_name} turned off",
        },
        "trigger_subtype": {
            "button_one": "Button one",
            "button_two": "Button two",
        },
        "extra_fields": {
            "brightness": "Brightness",
        },
        "extra_fields_descriptions": {
            "brightness": "The brightness level to set",
        },
    },
    "system_health": {
        "info": {
            "api_status": "API status",
            "connected_devices": "Connected devices",
        },
    },
    "config_panel": {
        "section_one": {
            "title": "Section one title",
            "subsection": {
                "item": "Subsection item",
            },
        },
        "_": {
            "common_key": "Common value",
        },
    },
    "application_credentials": {
        "description": "To configure this integration, you need to create an application",
    },
    "issues": {
        "firmware_update_required": {
            "title": "Firmware update required",
            "fix_flow": {
                "step": {
                    "confirm": {
                        "title": "Confirm firmware update",
                        "description": "Your device needs a firmware update",
                        "data": {
                            "confirm": "I understand",
                        },
                    },
                },
                "abort": {
                    "update_failed": "Update failed",
                },
            },
        },
        "deprecated_yaml": {
            "title": "Deprecated YAML configuration",
            "description": "YAML configuration is deprecated, please use the UI",
        },
    },
    "entity_component": {
        "_": {
            "name": "Test Integration",
            "state": {
                "on": "On",
                "off": "Off",
            },
            "state_attributes": {
                "mode": {
                    "name": "Mode",
                    "state": {
                        "auto": "Automatic",
                        "manual": "Manual",
                    },
                },
            },
        },
        "sensor": {
            "name": "Test Sensor",
            "state": {
                "idle": "Idle",
                "active": "Active",
            },
            "state_attributes": {
                "status": {
                    "name": "Status",
                    "state": {
                        "ok": "OK",
                        "error": "Error",
                    },
                },
            },
        },
    },
    "device": {
        "main_device": {
            "name": "Main device",
        },
        "secondary_device": {
            "name": "Secondary device",
        },
    },
    "entity": {
        "sensor": {
            "temperature": {
                "name": "Temperature",
                "state": {
                    "low": "Low",
                    "high": "High",
                },
                "state_attributes": {
                    "trend": {
                        "name": "Trend",
                        "state": {
                            "rising": "Rising",
                            "falling": "Falling",
                        },
                    },
                },
                "unit_of_measurement": "degrees",
            },
            "humidity": {
                "name": "Humidity",
            },
        },
        "binary_sensor": {
            "motion": {
                "name": "Motion",
                "state": {
                    "on": "Detected",
                    "off": "Clear",
                },
            },
        },
        "switch": {
            "power": {
                "name": "Power",
            },
        },
    },
    "exceptions": {
        "cannot_connect": {
            "message": "Cannot connect to {host}",
        },
        "invalid_credentials": {
            "message": "Invalid credentials for {username}",
        },
    },
    "services": {
        "set_value": {
            "name": "Set value",
            "description": "Sets a value on the device",
            "fields": {
                "value": {
                    "name": "Value",
                    "description": "The value to set",
                    "example": "100",
                },
                "target": {
                    "name": "Target",
                    "description": "The target device",
                },
            },
            "sections": {
                "advanced": {
                    "name": "Advanced options",
                    "description": "Advanced configuration options",
                },
            },
        },
        "reload": {
            "name": "Reload",
            "description": "Reloads the integration",
        },
    },
    "conditions": {
        "is_on": {
            "name": "Is on",
            "description": "Test if the device is on",
            "fields": {
                "entity_id": {
                    "name": "Entity",
                    "description": "The entity to check",
                    "example": "light.living_room",
                },
            },
        },
    },
    "triggers": {
        "turned_on": {
            "name": "Turned on",
            "description": "When the device turns on",
            "fields": {
                "entity_id": {
                    "name": "Entity",
                    "description": "The entity to monitor",
                    "example": "light.living_room",
                },
            },
        },
    },
    "conversation": {
        "agent": {
            "done": "Done",
        },
    },
    "common": {
        "on": "On",
        "off": "Off",
        "unknown": "Unknown",
    },
}


def test_gen_strings_schema(
    config: Config,
) -> None:
    """Test gen_strings_schema validates all string types."""
    integration = get_integration("test_integration", config)
    schema = translations.gen_strings_schema(config, integration)

    # Validate the sample strings - should not raise
    validated = schema(SAMPLE_STRINGS)

    assert validated == SAMPLE_STRINGS


@pytest.mark.parametrize(
    "translation_string",
    [
        "An example is: https://example.com.",
        "www.example.com",
        "http://example.com:8080",
        "WWW.EXAMPLE.COM",
        "HTTPS://www.example.com",
    ],
)
def test_no_placeholders_used_for_urls(translation_string: str) -> None:
    """Test that translation strings containing URLs are rejected."""
    schema = vol.Schema(translations.translation_value_validator)

    with pytest.raises(vol.Invalid):
        schema(translation_string)


@pytest.mark.parametrize(
    "translation_string",
    [
        "An example is: https://example.com.",
        "www.example.com",
        "http://example.com:8080",
        "WWW.EXAMPLE.COM",
        "HTTPS://www.example.com",
    ],
)
def test_allow_urls_in_translation_value(translation_string: str) -> None:
    """Test that URLs are allowed when allow_urls=True."""
    schema = vol.Schema(
        translations.custom_translation_value_validator(allow_urls=True)
    )

    # Should not raise
    schema(translation_string)
