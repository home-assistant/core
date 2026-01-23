---
title: Options flow
---

An integration that is configured via a config entry can expose options to the user to allow tweaking behavior of the integration, like which devices or locations should be integrated.

Config Entry Options uses the [Data Flow Entry framework](data_entry_flow_index.md) to allow users to update the options of a config entry. Components that want to support config entry options will need to define an Options Flow Handler.

## Options support

For an integration to support options it needs to have an `async_get_options_flow` method in its config flow handler. Calling it will return an instance of the components options flow handler.

```python
@staticmethod
@callback
def async_get_options_flow(
    config_entry: ConfigEntry,
) -> OptionsFlowHandler:
    """Create the options flow."""
    return OptionsFlowHandler()
```

## Flow handler

The Flow handler works just like the config flow handler, except that the first step in the flow will always be `async_step_init`. The current config entry details are available through the `self.config_entry` property.

```python
from homeassistant.config_entries import OptionsFlow

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("show_things"): bool,
    }
)
class OptionsFlowHandler(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
```

## Options flow with automatic reload

If the integration should be reloaded after the config options change, it can subclass from `OptionsFlowWithReload` instead of `OptionsFlow`. `OptionsFlowWithReload` will automatically reload the integration once the options change.

Since the most common reason to add an update listener is to reload the integration when the options have changed, `OptionsFlowWithReload` avoids the need for that listener.

```python
from homeassistant.config_entries import OptionsFlowWithReload

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("show_things"): bool,
    }
)
class MyOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
```

## Signal updates

If the integration should act on updated options, you can register an update listener to the config entry that will be called when the entry is updated. A listener is registered by adding the following to the `async_setup_entry` function in your integration's `__init__.py`.

```python
entry.async_on_unload(entry.add_update_listener(update_listener))
```

Using the above means the Listener is attached when the entry is loaded and detached at unload. The Listener shall be an async function that takes the same input as async_setup_entry. Options can then be accessed from `entry.options`.

```python
async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
```
