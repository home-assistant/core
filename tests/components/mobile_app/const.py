"""Constants for mobile_app tests."""
CALL_SERVICE = {
    "type": "call_service",
    "data": {"domain": "test", "service": "mobile_app", "service_data": {"foo": "bar"}},
}

FIRE_EVENT = {
    "type": "fire_event",
    "data": {"event_type": "test_event", "event_data": {"hello": "yo world"}},
}

REGISTER = {
    "app_data": {"foo": "bar"},
    "app_id": "io.homeassistant.mobile_app_test",
    "app_name": "Mobile App Tests",
    "app_version": "1.0.0",
    "device_name": "Test 1",
    "manufacturer": "mobile_app",
    "model": "Test",
    "os_name": "Linux",
    "os_version": "1.0",
    "supports_encryption": True,
}

REGISTER_CLEARTEXT = {
    "app_data": {"foo": "bar"},
    "app_id": "io.homeassistant.mobile_app_test",
    "app_name": "Mobile App Tests",
    "app_version": "1.0.0",
    "device_name": "Test 1",
    "manufacturer": "mobile_app",
    "model": "Test",
    "device_id": "mock-device-id",
    "os_name": "Linux",
    "os_version": "1.0",
    "supports_encryption": False,
}

RENDER_TEMPLATE = {
    "type": "render_template",
    "data": {"one": {"template": "Hello world"}},
}

UPDATE = {
    "app_data": {"foo": "bar"},
    "app_version": "2.0.0",
    "device_name": "Test 1",
    "manufacturer": "mobile_app",
    "model": "Test",
    "os_version": "1.0",
}

VALID_CONFIG = {
    "push": {
        "categories": [
            {
                "name": "Mobile_App Alarm",
                "identifier": "alarm",
                "actions": [
                    {
                        "identifier": "SOUND_ALARM",
                        "title": "Sound Alarm",
                        "activationMode": "background",
                        "authenticationRequired": True,
                        "destructive": True,
                        "behavior": "default",
                    },
                    {
                        "identifier": "SILENCE_ALARM",
                        "title": "Silence Alarm",
                        "activationMode": "background",
                        "authenticationRequired": True,
                        "destructive": False,
                        "behavior": "textInput",
                        "textInputButtonTitle": "Silencio!",
                        "textInputPlaceholder": "Placeholder",
                    },
                ],
            }
        ]
    },
    "actions": [
        {
            "name": "Fred",
            "background_color": "#000000",
            "label": {"text": "Hello, World", "color": "#ff0000"},
            "icon": {"icon": "an-icon", "color": "#ff0000"},
        },
        {
            "name": "George",
            "background_color": "#000000",
            "label": {"text": "Hello, World", "color": "#ff0000"},
            "icon": {"icon": "an-icon", "color": "#ff0000"},
        },
    ],
}
