---
title: "Integration service actions"
sidebar_label: "Custom actions"
---

Home Assistant provides ready-made actions for a lot of things, but it doesn't always cover everything. Instead of trying to change Home Assistant, it is preferred to add it as a service action under your own integration first. Once we see a pattern in these service actions, we can talk about generalizing them.

[Service actions should always be registered](/docs/core/integration-quality-scale/rules/action-setup) to ensure automations referencing them can be edited and validated, and to allow an informative error message when a service is called even if the integration has no loaded config entries. Register services in the integration's `async_setup` or `setup` function, not in the integration's `async_setup_entry` or in a platform's `async_setup_entry`, `async_setup_platform`, or `setup_platform`.

This is a simple "hello world" example to show the basics of registering a service action. To use this example, create the file `<config dir>/custom_components/hello_action/__init__.py` and copy the below example code.

Actions can be called from automations and from the actions "Developer tools" in the frontend.

```python
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType

DOMAIN = "hello_action"

ATTR_NAME = "name"
DEFAULT_NAME = "World"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    @callback
    def handle_hello(call: ServiceCall) -> None:
        """Handle the service action call."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.async_set("hello_action.hello", name)

    hass.services.async_register(DOMAIN, "hello", handle_hello)

    # Return boolean to indicate that initialization was successful.
    return True
```

To load the integration in Home Assistant is necessary to create a `manifest.json` and to add an entry in your `configuration.yaml`. When your component is loaded, a new service should be available to call.

```yaml
# configuration.yaml entry
hello_action:
```

An example of `manifest.json`:

```json
{
    "domain": "hello_action",
    "name": "Hello Action",
    "documentation": "https://developers.home-assistant.io/docs/dev_101_services",
    "iot_class": "local_push",
    "version": "0.1.0"
}
```

Open the frontend and in the sidebar, click the first icon in the developer tool section. This will open the Actions developer tool. On the right, find your action and click on it. This will automatically fill in the correct values.

Pressing "Perform action" will now call your service action without any parameters. This will cause your service action to create a state with the default name 'World'. If you want to specify the name, you have to specify a parameter by providing it through service action Data. In YAML mode, add the following and press "Perform Service" again.

```yaml
service: hello_action.hello
data:
  name: Planet
```

The service action will now overwrite the previous state with "Planet".

## Service action descriptions

Adding actions is only useful if users know about them. In Home Assistant we use a `services.yaml` as part of your integration to describe the service actions.

Actions are published under the domain name of your integration, so in `services.yaml` we only use the service action name as the base key.

### Service action description example

```yaml
# Example services.yaml entry

# Service ID
set_speed:
  # If the service action accepts entity IDs, target allows the user to specify
  # entities by entity, device, or area. If `target` is specified, `entity_id`
  # should not be  defined in the `fields` map. By default it shows only targets
  # matching entities from the same domain as the action, but if further
  # customization is required, target supports the entity, device, and area
  # selectors (https://www.home-assistant.io/docs/blueprint/selectors/).
  # Entity selector parameters will automatically be applied to device and area,
  # and device selector parameters will automatically be applied to area.
  target:
    entity:
      domain: fan
      # If not all entities from the action's domain support an action, entities
      # can be further filtered by the `supported_features` state attribute. An
      # entity will only be possible to select if it supports at least one of the
      # listed supported features.
      supported_features:
        - fan.FanEntityFeature.SET_SPEED
        # If a service action requires more than one supported feature, the item
        # should be given as a list of required supported features. For example,
        # if the service action requires both SET_SPEED and OSCILLATE it would
        # be expressed like this
        - - fan.FanEntityFeature.SET_SPEED
          - fan.FanEntityFeature.OSCILLATE
  # Different fields that your service action accepts
  fields:
    # Key of the field
    speed:
      # Whether or not field is required (default = false)
      required: true
      # Advanced fields are only shown when the advanced mode is enabled for the user
      # (default = false)
      advanced: true
      # Example value that can be passed for this field
      example: "low"
      # The default field value
      default: "high"
      # Selector (https://www.home-assistant.io/docs/blueprint/selectors/) to control
      # the input UI for this field
      selector:
        select:
          translation_key: "fan_speed"
          options:
            - "off"
            - "low"
            - "medium"
            - "high"
    # Fields can be grouped in collapsible sections, this is useful to initially hide
    # advanced fields and to group related fields. Note that the collapsible section
    # only affect presentation to the user, service action data will not be nested.
    advanced_fields:
      # Whether or not the section is initially collapsed (default = false)
      collapsed: true
      # Input fields in this section
      fields:
        speed_pct:
          selector:
            number:
              min: 0
              max: 100
```

:::info
The name and description of the service actions are set in our [translations](/docs/internationalization/core#services) and not in the service action description. Each service action and service action field must have a matching translation defined. Description placeholders allow you to exclude elements like URLs from translations.

```python
...
    hass.services.async_register(
      DOMAIN,
      "hello", handle_hello,
      description_placeholders={"docs_url": "https://example.com/hello_world"},
    )
...
```

:::

### Grouping of service action fields

Input fields can be visually grouped in sections. Grouping input fields by sections influences
only how the inputs are displayed to the user, and not how service action data is structured.

In the [service action description example](#service-action-description-example), the `speed_pct`
input field is inside an initially collapsed section `advanced_fields`.
The service action data for the service in the example is `{"speed_pct": 50}`, not
`{"advanced_fields": {"speed_pct": 50}}`.

### Filtering service action fields

In some cases, entities from an action's domain may not support all service action fields.
By providing a `filter` for the field description, the field will only be shown if at
least one selected entity supports the field according to the configured filter.

A filter must specify either `supported_features` or `attribute`, combing both is not
supported.

A `supported_features` filter is specified by of a list of supported features. The field
will be shown if at least one selected entity supports at least one of the listed features.

An `attribute` filter combines an attribute with a list of values. The field will be
shown if at least one selected entity's attribute is set to one of the listed attribute states.
If the attribute state is a list, the field will be shown if at least one item in a selected
entity's attribute state is set to one of the listed attribute states.

This is a partial example of a field which is only shown if at least one selected entity
supports `ClimateEntityFeature.TARGET_TEMPERATURE`:

```yaml
  fields:
    temperature:
      name: Temperature
      description: New target temperature for HVAC.
      filter:
        supported_features:
          - climate.ClimateEntityFeature.TARGET_TEMPERATURE
```

This is a partial example of a field which is only shown if at least one selected entity's
`supported_color_modes` attribute includes either `light.ColorMode.COLOR_TEMP` or
`light.ColorMode.HS`:

```yaml
    color_temp:
      name: Color temperature
      description: Color temperature for the light in mireds.
      filter:
        attribute:
          supported_color_modes:
            - light.ColorMode.COLOR_TEMP
            - light.ColorMode.HS
```

## Icons

Actions can also have icons. These icons are used in the Home Assistant UI when displaying the service action in places like the automation and script editors.

The icon to use for each service action can be defined in the `icons.json` translation file in the integration folder, under the `services` key. The key should be the service action name, and the value should be the icon to use.

The following example shows how to provide icons for the `turn_on` and `turn_off` service actions of an integration:

```json
{
  "services": {
    "turn_on": {"service": "mdi:lightbulb-on"},
    "turn_off": {"service": "mdi:lightbulb-off"}
  }
}
```

In addition, icons can optionally be specified for collapsible sections.

The following example shows how to provide an icon for the `advanced_options` section:

```json
{
  "services": {
    "start_brewing": {
      "service": "mdi:flask",
      "sections": {
        "advanced_options": "mdi:test-tube"
      }
    }
  }
}
```


## Entity service actions

Sometimes you want to provide extra actions to control your entities. For example, the Sonos integration provides action to group and ungroup devices. Entity service actions are special because there are many different ways a user can specify entities. It can use areas, a group or a list of entities.

Register entity service actions with `homeassistant.helpers.service.async_register_platform_entity_service`. Register actions under your integration domain, e.g. `sonos`, not under the platform domain, e.g. `media_player`. You can pass a schema to `async_register_platform_entity_service` if the entity service action has fields. The schema can be:

- A dictionary which will automatically be passed to `cv._make_entity_service_schema`
- A validator returned by `cv._make_entity_service_schema`
- A validator returned by `cv._make_entity_service_schema`, wrapped in a `vol.Schema`
- A validator returned by `cv._make_entity_service_schema`, wrapped in a `vol.All`

Example code added to `homeassistant/components/sonos/__init__.py`:

```python
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv, service
import voluptuous as vol

DOMAIN = "sonos"
SERVICE_SET_TIMER = "set_sleep_timer"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sonos integration."""

    # This will call each targeted entity's `set_sleep_timer` method with `sleep_time=VALUE`
    service.async_register_platform_entity_service(
         hass,
         DOMAIN,
         SERVICE_SET_TIMER,
         entity_domain=MEDIA_PLAYER_DOMAIN,
         schema={vol.Required("sleep_time"): cv.time_period},
         func="set_sleep_timer",
     )
    return True
```

If you need more control over the service action call, you can also pass an async function that will be called instead of `"set_sleep_timer"`:

```python
async def custom_set_sleep_timer(entity, service_call):
    await entity.set_sleep_timer(service_call.data['sleep_time'])
```

## Response data

Actions may respond to an action call with data for powering more advanced automations. There are some additional implementation requirements:

- Response data must be a `dict` and serializable in JSON [`homeassistant.util.json.JsonObjectType`](https://github.com/home-assistant/home-assistant/blob/master/homeassistant/util/json.py) in order to interoperate with other parts of the system, such as the frontend.
- Errors must be raised as exceptions just like any other service action call as
we do not want end users to need complex error handling in scripts and automations.
The response data should not contain error codes used for error handling.

Example code:

```python
import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.util.json import JsonObjectType

SEARCH_ITEMS_SERVICE_NAME = "search_items"
SEARCH_ITEMS_SCHEMA = vol.Schema({
    vol.Required("start"): datetime.datetime,
    vol.Required("end"): datetime.datetime,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""

    async def search_items(call: ServiceCall) -> ServiceResponse:
        """Search in the date range and return the matching items."""
        items = await my_client.search(call.data["start"], call.data["end"])
        return {
            "items": [
                {
                    "summary": item["summary"],
                    "description": item["description"],
                } for item in items
            ],
        }

    hass.services.async_register(
        DOMAIN,
        SEARCH_ITEMS_SERVICE_NAME,
        search_items,
        schema=SEARCH_ITEMS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
```

The use of response data is meant for cases that do not fit the Home Assistant state. For example, a response stream of objects. Conversely, response data should not be used for cases that are a fit for entity state. For example, a temperature value should just be a sensor.

### Supporting response data

Action calls are registered with a `SupportsResponse` value to indicate response data is supported.

| Value      | Description                                                                                                                                                                                                                       |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OPTIONAL` | Performs an action and can optionally return response data. The service action should conditionally check the `ServiceCall` property `return_response` to decide whether or not response data should be returned, or `None`. |
| `ONLY`     | Doesn't perform any actions and always returns response data.                                                                                                                                                         |
