"""Constants for mobile_app tests."""
CALL_SERVICE = {
    'type': 'call_service',
    'data': {
        'domain': 'test',
        'service': 'mobile_app',
        'service_data': {
            'foo': 'bar'
        }
    }
}

FIRE_EVENT = {
    'type': 'fire_event',
    'data': {
        'event_type': 'test_event',
        'event_data': {
            'hello': 'yo world'
        }
    }
}

REGISTER = {
    'app_data': {'foo': 'bar'},
    'app_id': 'io.homeassistant.mobile_app_test',
    'app_name': 'Mobile App Tests',
    'app_version': '1.0.0',
    'device_name': 'Test 1',
    'manufacturer': 'mobile_app',
    'model': 'Test',
    'os_version': '1.0',
    'supports_encryption': True
}

RENDER_TEMPLATE = {
    'type': 'render_template',
    'data': {
        'template': 'Hello world'
    }
}

UPDATE = {
    'app_data': {'foo': 'bar'},
    'app_version': '2.0.0',
    'device_name': 'Test 1',
    'manufacturer': 'mobile_app',
    'model': 'Test',
    'os_version': '1.0'
}
