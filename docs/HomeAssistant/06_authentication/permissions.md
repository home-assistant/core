---
title: "Permissions"
---

:::info
This is an experimental feature that is not enabled or enforced yet
:::

Permissions limit the things a user has access to or can control. Permissions are attached to groups, of which a user can be a member. The combined permissions of all groups a user is a member of decides what a user can and cannot see or control.

Permissions do not apply to the user that is flagged as "owner". This user  will always have access to everything.

## General permission structure

Policies are dictionaries that at the root level consist of different categories of permissions. In the current implementation this is limited to just entities.

```python
{
    "entities": {
        # …
    }
}
```

Each category can further split into subcategories that describe parts of that category.

```python
{
    "entities": {
        "domains": {
            # …
        },
        "entity_ids": {
            # …
        },
    }
}
```

If a category is omitted, the user will not have permission to that category.

When defining a policy, any dictionary value at any place can be replaced with `True` or `None`. `True` means that permission is granted and `None` means use default, which is deny access.

## Entities

Entity permissions can be set on a per entity and per domain basis using the subcategories `entity_ids`, `device_ids`, `area_ids` and `domains`. You can either grant all access by setting the value to `True`, or you can specify each entity individually using the "read", "control", "edit" permissions.

The system will return the first matching result, based on the order: `entity_ids`, `device_ids`, `area_ids`, `domains`, `all`.

```json
{
  "entities": {
    "domains": {
      "switch": true
    },
    "entity_ids": {
      "light.kitchen": {
        "read": true,
        "control": true
      }
    }
  }
}
```

## Merging policies

If a user is a member of multiple groups, the groups permission policies will be combined into a single policy at runtime. When merging policies, we will look at each level of the dictionary and compare the values for each source using the following methodology:

1. If any of the values is `True`, the merged value becomes `True`.
2. If any value is a dictionary, the merged value becomes a dictionary created by recursively checking each value using this methodology.
3. If all values are `None`, the merged value becomes `None`.

Let's look at an example:

```python
{
    "entities": {
        "entity_ids": {
            "light.kitchen": True
        }
    }
}
```

```python
{
    "entities": {
        "entity_ids": True
    }
}
```

Once merged becomes

```python
{
    "entities": {
        "entity_ids": True
    }
}
```

## Checking permissions

We currently have two different permission checks: can the user do the read/control/edit operation on an entity, and is the user an admin and thus allowed to change this configuration setting.

Certain APIs will always be accessible to all users, but might offer a limited scope based on the permissions, like rendering a template.

### Checking permissions

To check a permission, you will need to have access to the user object. Once you have the user object, checking the permission is easy.

```python
from homeassistant.exceptions import Unauthorized
from homeassistant.permissions.const import POLICY_READ, POLICY_CONTROL, POLICY_EDIT

# Raise error if user is not an admin
if not user.is_admin:
    raise Unauthorized()


# Raise error if user does not have access to control an entity
# Available policies: POLICY_READ, POLICY_CONTROL, POLICY_EDIT
if not user.permissions.check_entity(entity_id, POLICY_CONTROL):
    raise Unauthorized()
```

### The context object

All service actions, fired events and states in Home Assistant have a context object. This object allows us to attribute changes to events and actions. These context objects also contain a user id, which is used for checking the permissions.

It's crucial for permission checking that actions taken on behalf of the user are done with a context containing the user ID. If you are in a service action handler, you should reuse the incoming context `call.context`. If you are inside a WebSocket API or Rest API endpoint, you should create a context with the correct user:

```python
from homeassistant.core import Context

await hass.services.async_call(
    "homeassistant", "stop", context=Context(user_id=user.id), blocking=True
)
```

### If a permission check fails

When you detect an unauthorized action, you should raise the `homeassistant.exceptions.Unauthorized` exception. This exception will cancel the current action and notifies the user that their action is unauthorized.

The `Unauthorized` exception has various parameters, to identify the permission check that failed. All fields are optional.

| # Not all actions have an ID (like adding config entry)
| # We then use this fallback to know what category was unauth

| Parameter | Description
| --------- | -----------
| context | The context of the current call.
| user_id | The user ID that we tried to operate on.
| entity_id | The entity ID that we tried to operate on.
| config_entry_id | The config entry ID that we tried to operate on.
| perm_category | The permission category that we tested. Only necessary if we don't have an object ID that the user tried to operate on (like when we create a config entry).
| permission | The permission that we tested, ie `POLICY_READ`.

### Securing a service action handler

Actions allow a user to control entities or with the integration as a whole. A service action uses the attached context to see which user invoked the command. Because context is used, it is important that you also pass the call context to all service action.

All service actions that are registered via the entity component (`component.async_register_entity_service()`) will automatically have their permissions checked.

#### Checking entity permissions

Your service action handler will need to check the permissions for each entity that it will act on.

```python
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.auth.permissions.const import POLICY_CONTROL


async def handle_entity_service(call):
    """Handle a service action call."""
    entity_ids = call.data["entity_id"]

    for entity_id in entity_ids:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)

            if user is None:
                raise UnknownUser(
                    context=call.context,
                    entity_id=entity_id,
                    permission=POLICY_CONTROL,
                )

            if not user.permissions.check_entity(entity_id, POLICY_CONTROL):
                raise Unauthorized(
                    context=call.context,
                    entity_id=entity_id,
                    permission=POLICY_CONTROL,
                )

        # Do action on entity


async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "my_service", handle_entity_service)
    return True
```

#### Checking admin permission

Starting Home Assistant 0.90, there is a special decorator to help protect
service actions that require admin access.

```python
# New in Home Assistant 0.90
async def handle_admin_service(call):
    """Handle a service action call."""
    # Do admin action


async def async_setup(hass, config):
    hass.helpers.service.async_register_admin_service(
        DOMAIN, "my_service", handle_admin_service, vol.Schema({})
    )
    return True
```

### Securing a REST API endpoint

```python
from homeassistant.core import Context
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.exceptions import Unauthorized


class MyView(HomeAssistantView):
    """View to handle Status requests."""

    url = "/api/my-component/my-api"
    name = "api:my-component:my-api"

    async def post(self, request):
        """Notify that the API is running."""
        hass = request.app["hass"]
        user = request["hass_user"]

        if not user.is_admin:
            raise Unauthorized()

        hass.bus.async_fire(
            "my-component-api-running", context=Context(user_id=user.id)
        )

        return self.json_message("Done.")
```

### Securing a Websocket API endpoint

Verifying permissions in a Websocket API endpoint can be done by accessing the
user via `connection.user`. If you need to check admin access, you can use the
built-in `@require_admin` decorator.

```python
from homeassistant.components import websocket_api


async def async_setup(hass, config):
    websocket_api.async_register_command(hass, websocket_create)
    return True


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required("type"): "my-component/my-action",}
)
async def websocket_create(hass, connection, msg):
    """Create a user."""
    # Do action
```
