"""Entity tests for mobile_app."""
# pylint: disable=redefined-outer-name,unused-import
import logging

from . import (authed_api_client, create_registrations,  # noqa: F401
               webhook_client)  # noqa: F401

_LOGGER = logging.getLogger(__name__)


async def test_sensor(hass, create_registrations, webhook_client):  # noqa: F401, F811, E501
    """Test that sensors can be registered and updated."""
    webhook_id = create_registrations[1]['webhook_id']
    webhook_url = '/api/webhook/{}'.format(webhook_id)

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            'type': 'register_sensor',
            'data': {
                'attributes': {
                    'foo': 'bar'
                },
                'device_class': 'battery',
                'icon': 'mdi:battery',
                'name': 'Battery State',
                'state': 100,
                'type': 'sensor',
                'unique_id': 'battery_state',
                'unit_of_measurement': '%'
            }
        }
    )

    assert reg_resp.status == 201

    json = await reg_resp.json()
    assert json == {'status': 'registered'}

    entity = hass.states.get('sensor.battery_state')
    assert entity is not None

    assert entity.attributes['device_class'] == 'battery'
    assert entity.attributes['icon'] == 'mdi:battery'
    assert entity.attributes['unit_of_measurement'] == '%'
    assert entity.attributes['foo'] == 'bar'
    assert entity.domain == 'sensor'
    assert entity.name == 'Battery State'
    assert entity.state == '100'

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            'type': 'update_sensor_states',
            'data': [
                {
                    'icon': 'mdi:battery-unknown',
                    'state': 123,
                    'type': 'sensor',
                    'unique_id': 'battery_state'
                }
            ]
        }
    )

    assert update_resp.status == 200

    updated_entity = hass.states.get('sensor.battery_state')
    assert updated_entity.state == '123'


async def test_sensor_must_register(hass, create_registrations,  # noqa: F401, F811, E501
                                    webhook_client):  # noqa: F401, F811, E501
    """Test that sensors must be registered before updating."""
    webhook_id = create_registrations[1]['webhook_id']
    webhook_url = '/api/webhook/{}'.format(webhook_id)
    resp = await webhook_client.post(
        webhook_url,
        json={
            'type': 'update_sensor_states',
            'data': [
                {
                    'state': 123,
                    'type': 'sensor',
                    'unique_id': 'battery_state'
                }
            ]
        }
    )

    assert resp.status == 200

    json = await resp.json()
    assert json['battery_state']['success'] is False
    assert json['battery_state']['error']['code'] == 'not_registered'


async def test_sensor_id_no_dupes(hass, create_registrations,  # noqa: F401, F811, E501
                                  webhook_client):  # noqa: F401, F811, E501
    """Test that sensors must have a unique ID."""
    webhook_id = create_registrations[1]['webhook_id']
    webhook_url = '/api/webhook/{}'.format(webhook_id)

    payload = {
        'type': 'register_sensor',
        'data': {
            'attributes': {
                'foo': 'bar'
            },
            'device_class': 'battery',
            'icon': 'mdi:battery',
            'name': 'Battery State',
            'state': 100,
            'type': 'sensor',
            'unique_id': 'battery_state',
            'unit_of_measurement': '%'
        }
    }

    reg_resp = await webhook_client.post(webhook_url, json=payload)

    assert reg_resp.status == 201

    reg_json = await reg_resp.json()
    assert reg_json == {'status': 'registered'}

    dupe_resp = await webhook_client.post(webhook_url, json=payload)

    assert dupe_resp.status == 409

    dupe_json = await dupe_resp.json()
    assert dupe_json['success'] is False
    assert dupe_json['error']['code'] == 'duplicate_unique_id'
