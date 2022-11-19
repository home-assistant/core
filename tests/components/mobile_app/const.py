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

REGISTER_ANDROID = {
    "app_data": {"foo": "bar"},
    "app_id": "io.homeassistant.mobile_app_test",
    "app_name": "Mobile App Tests",
    "app_version": "1.0.0",
    "device_name": "Android Device",
    "manufacturer": "android_vendor",
    "model": "Test Android",
    "device_id": "mock-device-android",
    "os_name": "Android",
    "os_version": "31",
    "supports_encryption": True,
}

REGISTER_IOS = {
    "app_data": {"foo": "bar"},
    "app_id": "io.homeassistant.mobile_app_test",
    "app_name": "Mobile App Tests",
    "app_version": "1.0.0",
    "device_name": "iOS Device",
    "manufacturer": "ios_vendor",
    "model": "Test iOS",
    "device_id": "mock-device-ios",
    "os_name": "iOS",
    "os_version": "14.0",
    "supports_encryption": True,
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
