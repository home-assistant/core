---
title: "WebSocket API"
---

Home Assistant hosts a WebSocket API at `/api/websocket`. This API can be used to stream information from a Home Assistant instance to any client that implements WebSockets. We maintain a [JavaScript library](https://github.com/home-assistant/home-assistant-js-websocket) which we use in our frontend.

## Server states

1. Client connects.
1. Authentication phase starts.
    - Server sends `auth_required` message.
    - Client sends `auth` message.
    - If `auth` message correct: go to 3.
    - Server sends `auth_invalid`. Go to 6.
1. Send `auth_ok` message
1. Authentication phase ends.
1. Command phase starts.
    1. Client can send commands.
    1. Server can send results of previous commands.
1. Client or server disconnects session.

During the command phase, the client attaches a unique identifier to each message. The server will add this identifier to each message so that the client can link each message to its origin.

## Message format

Each API message is a JSON serialized object containing a `type` key. After the authentication phase messages also must contain an `id`, an integer that the caller can use to correlate messages to responses.

Example of an auth message:

```json
{
  "type": "auth",
  "access_token": "ABCDEFGHIJKLMNOPQ"
}
```

```json
{
   "id": 5,
   "type":"event",
   "event":{
      "data":{},
      "event_type":"test_event",
      "time_fired":"2016-11-26T01:37:24.265429+00:00",
      "origin":"LOCAL"
   }
}
```

## Authentication phase

When a client connects to the server, the server sends out `auth_required`.

```json
{
  "type": "auth_required",
  "ha_version": "2021.5.3"
}
```

The first message from the client should be an auth message. You can authorize with an access token.

```json
{
  "type": "auth",
  "access_token": "ABCDEFGH"
}
```

If the client supplies valid authentication, the authentication phase will complete by the server sending the `auth_ok` message:

```json
{
  "type": "auth_ok",
  "ha_version": "2021.5.3"
}
```

If the data is incorrect, the server will reply with `auth_invalid` message and disconnect the session.

```json
{
  "type": "auth_invalid",
  "message": "Invalid password"
}
```

## Feature enablement phase

Clients that supports features that needs enabling should as their first message (with `"id": 1`) send a message in the form:

```
{
  "id": 1,
  "type": "supported_features",
  "features": { coalesce_messages: 1 }
}
```

As of now the only feature supported is 'coalesce_messages' which result in messages being sent coalesced in bulk instead of individually. 

## Command phase

During this phase the client can give commands to the server. The server will respond to each command with a `result` message indicating when the command is done and if it was successful along with the context of the command.

```json
{
  "id": 6,
  "type": "result",
  "success": true,
  "result": {
    "context": {
      "id": "326ef27d19415c60c492fe330945f954",
      "parent_id": null,
      "user_id": "31ddb597e03147118cf8d2f8fbea5553"
    }
  }
}
```

## Subscribe to events

The command `subscribe_events` will subscribe your client to the event bus. You can either listen to all events or to a specific event type. If you want to listen to multiple event types, you will have to send multiple `subscribe_events` commands.

```json
{
  "id": 18,
  "type": "subscribe_events",
  // Optional
  "event_type": "state_changed"
}
```

The server will respond with a result message to indicate that the subscription is active.

```json
{
  "id": 18,
  "type": "result",
  "success": true,
  "result": null
}
```

For each event that matches, the server will send a message of type `event`. The `id` in the message will point at the original `id` of the `listen_event` command.

```json
{
   "id": 18,
   "type":"event",
   "event":{
      "data":{
         "entity_id":"light.bed_light",
         "new_state":{
            "entity_id":"light.bed_light",
            "last_changed":"2016-11-26T01:37:24.265390+00:00",
            "state":"on",
            "attributes":{
               "rgb_color":[
                  254,
                  208,
                  0
               ],
               "color_temp":380,
               "supported_features":147,
               "xy_color":[
                  0.5,
                  0.5
               ],
               "brightness":180,
               "white_value":200,
               "friendly_name":"Bed Light"
            },
            "last_updated":"2016-11-26T01:37:24.265390+00:00",
            "context": {
               "id": "326ef27d19415c60c492fe330945f954",
               "parent_id": null,
               "user_id": "31ddb597e03147118cf8d2f8fbea5553"
            }
         },
         "old_state":{
            "entity_id":"light.bed_light",
            "last_changed":"2016-11-26T01:37:10.466994+00:00",
            "state":"off",
            "attributes":{
               "supported_features":147,
               "friendly_name":"Bed Light"
            },
            "last_updated":"2016-11-26T01:37:10.466994+00:00",
            "context": {
               "id": "e4af5b117137425e97658041a0538441",
               "parent_id": null,
               "user_id": "31ddb597e03147118cf8d2f8fbea5553"
            }
         }
      },
      "event_type":"state_changed",
      "time_fired":"2016-11-26T01:37:24.265429+00:00",
      "origin":"LOCAL",
      "context": {
         "id": "326ef27d19415c60c492fe330945f954",
         "parent_id": null,
         "user_id": "31ddb597e03147118cf8d2f8fbea5553"
      }
   }
}
```

## Subscribe to trigger

You can also subscribe to one or more triggers with `subscribe_trigger`. These are the same triggers syntax as used for [automation triggers](https://www.home-assistant.io/docs/automation/trigger/). You can define one or a list of triggers.

```json
{
    "id": 2,
    "type": "subscribe_trigger",
    "trigger": {
        "platform": "state",
        "entity_id": "binary_sensor.motion_occupancy",
        "from": "off",
        "to":"on"
    }
}
```

As a response you get:

```json
{
 "id": 2,
 "type": "result",
 "success": true,
 "result": null
}
```

For each trigger that matches, the server will send a message of type `trigger`. The `id` in the message will point at the original `id` of the `subscribe_trigger` command. Note that your variables will be different based on the used trigger.

```json
{
    "id": 2,
    "type": "event",
    "event": {
        "variables": {
            "trigger": {
                "id": "0",
                "idx": "0",
                "platform": "state",
                "entity_id": "binary_sensor.motion_occupancy",
                "from_state": {
                    "entity_id": "binary_sensor.motion_occupancy",
                    "state": "off",
                    "attributes": {
                        "device_class": "motion",
                        "friendly_name": "motion occupancy"
                    },
                    "last_changed": "2022-01-09T10:30:37.585143+00:00",
                    "last_updated": "2022-01-09T10:33:04.388104+00:00",
                    "context": {
                        "id": "90e30ad8e6d0c218840478d3c21dd754",
                        "parent_id": null,
                        "user_id": null
                    }
                },
                "to_state": {
                    "entity_id": "binary_sensor.motion_occupancy",
                    "state": "on",
                    "attributes": {
                        "device_class": "motion",
                        "friendly_name": "motion occupancy"
                    },
                    "last_changed": "2022-01-09T10:33:04.391956+00:00",
                    "last_updated": "2022-01-09T10:33:04.391956+00:00",
                    "context": {
                        "id": "9b263f9e4e899819a0515a97f6ddfb47",
                        "parent_id": null,
                        "user_id": null
                    }
                },
                "for": null,
                "attribute": null,
                "description": "state of binary_sensor.motion_occupancy"
            }
        },
        "context": {
            "id": "9b263f9e4e899819a0515a97f6ddfb47",
            "parent_id": null,
            "user_id": null
        }
    }
}
```

### Unsubscribing from events

You can unsubscribe from previously created subscriptions. Pass the id of the original subscription command as value to the subscription field.

```json
{
  "id": 19,
  "type": "unsubscribe_events",
  "subscription": 18
}
```

The server will respond with a result message to indicate that unsubscribing was successful.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": null
}
```

## Fire an event

This will fire an event on the Home Assistant event bus.

```json
{
  "id": 24,
  "type": "fire_event",
  "event_type": "mydomain_event",
  // Optional
  "event_data": {
    "device_id": "my-device-id",
    "type": "motion_detected"
  }
}
```

The server will respond with a result message to indicate that the event was fired successful.

```json
{
  "id": 24,
  "type": "result",
  "success": true,
  "result": {
    "context": {
      "id": "326ef27d19415c60c492fe330945f954",
      "parent_id": null,
      "user_id": "31ddb597e03147118cf8d2f8fbea5553"
    }
  }
}
```

## Calling a service action

This will call a service action in Home Assistant. Right now there is no return value. The client can listen to `state_changed` events if it is interested in changed entities as a result of a call.

```json
{
  "id": 24,
  "type": "call_service",
  "domain": "light",
  "service": "turn_on",
  // Optional
  "service_data": {
    "color_name": "beige",
    "brightness": "101"
  }
  // Optional
  "target": {
    "entity_id": "light.kitchen"
  }
  // Must be included for service actions that return response data
  "return_response": true
}
```

The server will indicate with a message indicating that the action is done executing.

```json
{
  "id": 24,
  "type": "result",
  "success": true,
  "result": {
    "context": {
      "id": "326ef27d19415c60c492fe330945f954",
      "parent_id": null,
      "user_id": "31ddb597e03147118cf8d2f8fbea5553"
    },
    "response": null
  }
}
```

The `result` of the call will always include a `response` to account for service actions that support responses. When an action that doesn't support responses is called, the value of `response` will be `null`.

## Fetching states

This will get a dump of all the current states in Home Assistant.

```json
{
  "id": 19,
  "type": "get_states"
}
```

The server will respond with a result message containing the states.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": [ ... ]
}
```

## Fetching config

This will get a dump of the current config in Home Assistant.

```json
{
  "id": 19,
  "type": "get_config"
}
```

The server will respond with a result message containing the config.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": { ... }
}
```

## Fetching service actions

This will get a dump of the current service actions in Home Assistant.

```json
{
  "id": 19,
  "type": "get_services"
}
```

The server will respond with a result message containing the service actions.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": { ... }
}
```

## Fetching panels

This will get a dump of the current registered panels in Home Assistant.

```json
{
  "id": 19,
  "type": "get_panels"
}
```

The server will respond with a result message containing the current registered panels.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": [ ... ]
}
```

## Pings and pongs

The API supports receiving a ping from the client and returning a pong. This serves as a heartbeat to ensure the connection is still alive:

```json
{
    "id": 19,
    "type": "ping"
}
```

The server must send a pong back as quickly as possible, if the connection is still active:

```json
{
    "id": 19,
    "type": "pong"
}
```

## Validate config

This command allows you to validate triggers, conditions and action configurations. The keys `trigger`, `condition` and `action` will be validated as if part of an automation (so a list of triggers/conditions/actions is also allowed). All fields are optional and the result will only contain keys that were passed in.

```json
{
  "id": 19,
  "type": "validate_config",
  "trigger": ...,
  "condition": ...,
  "action": ...
}
```

The server will respond with the validation results. Only fields will be included in the response that were also included in the command message.

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": {
    "trigger": {"valid": true, "error": null},
    "condition": {"valid": false, "error": "Invalid condition specified for data[0]"},
    "action": {"valid": true, "error": null}
  }
}
```

## Extract from target

This command allows you to extract entities, devices, and areas from one or multiple targets.

```json
{
  "id": 19,
  "type": "extract_from_target",
  "target": {
    "entity_id": ["group.kitchen"],
    "device_id": ["device_abc123"],
    "area_id": ["kitchen"],
    "label_id": ["smart_lights"]
  },
  // Optional: expand group entities to their members (default: false)
  "expand_group": true
}
```

The target parameter follows the same structure as service call targets.

The server will respond with the information extracted from the target:

```json
{
  "id": 19,
  "type": "result",
  "success": true,
  "result": {
    "referenced_entities": ["light.kitchen", "switch.kitchen", "light.living_room", "switch.bedroom"],
    "referenced_devices": ["device_abc123", "device_def456"],
    "referenced_areas": ["kitchen", "living_room"],
    "missing_devices": [],
    "missing_areas": [],
    "missing_floors": [],
    "missing_labels": []
  }
}
```

The response includes:
- `referenced_entities`: All entity IDs that would be targeted (includes entities from devices/areas/labels)
- `referenced_devices`: All device IDs that were referenced
- `referenced_areas`: All area IDs that were referenced
- `missing_devices`: Device IDs that don't exist
- `missing_areas`: Area IDs that don't exist
- `missing_floors`: Floor IDs that don't exist
- `missing_labels`: Label IDs that don't exist

When `expand_group` is set to `true`, group entities will be expanded to include their member entities instead of the group entity itself.

## Get triggers/conditions/services for target

The `get_triggers_for_target`, `get_conditions_for_target`, and `get_services_for_target` commands allow you to get all applicable triggers, conditions, and services for entities of a given target. The three commands share the same input and output format.

```json
{
  "id": 20,
  "type": "get_triggers_for_target",
  "target": {
    "entity_id": ["light.kitchen", "light.living_room"],
    "device_id": ["device_abc123"],
    "area_id": ["bedroom"],
    "label_id": ["smart_lights"]
  },
  // Optional: expand group entities to their members (default: true)
  "expand_group": true
}
```

The target parameter follows the same structure as service call targets.

The server will respond with a set of trigger/condition/service identifiers that are applicable to any of the entities of the target, in the format `domain.trigger_name`:

```json
{
  "id": 20,
  "type": "result",
  "success": true,
  "result": [
    "homeassistant.event",
    "homeassistant.state",
    "light.turned_on",
    "light.turned_off",
    "light.toggle"
  ]
}
```

When `expand_group` is set to `true` (default), group entities will be expanded to include their member entities, and triggers applicable to any member will be included in the results. Otherwise, only triggers applicable to the group entities themselves will be included.

## Error handling

If an error occurs, the `success` key in the `result` message will be set to `false`. It will contain an `error` key containing an object with two keys: `code` and `message`.

```json
{
   "id": 12,
   "type":"result",
   "success": false,
   "error": {
      "code": "invalid_format",
      "message": "Message incorrectly formatted: expected str for dictionary value @ data['event_type']. Got 100"
   }
}
```

### Error handling during service action calls and translations

The JSON below shows an example of an error response. If `HomeAssistantError` error (or a subclass of `HomeAssistantError`) is handled, translation information, if set, will be added to the response. 

When handling `ServiceValidationError` (`service_validation_error`) a stack trace is printed to the logs at debug level only.

```json
{
   "id": 24,
   "type":"result",
   "success": false,
   "error": {
      "code": "service_validation_error",
      "message": "Option 'custom' is not a supported mode.",
      "translation_key": "unsupported_mode",
      "translation_domain": "kitchen_sink",
      "translation_placeholders": {
        "mode": "custom"
      }
   }
}
```

[Read more](/docs/core/platform/raising_exceptions) about raising exceptions or and the [localization of exceptions](/docs/internationalization/core/#exceptions).
