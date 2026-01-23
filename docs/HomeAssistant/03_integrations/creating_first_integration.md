---
title: "Creating your first integration"
---

Alright, so it's time to write your first code for your integration. AWESOME. Don't worry, we've tried hard to keep it as easy as possible. From a Home Assistant development environment, type the following and follow the instructions:

```shell
python3 -m script.scaffold integration
```

This will set you up with everything that you need to build an integration that is able to be set up via the user interface. More extensive examples of integrations are available from [our example repository](https://github.com/home-assistant/example-custom-config/tree/master/custom_components/).

:::tip
This example repository shows custom integrations that live in the `<config_dir>/custom_components` directory. These MUST have a `version` key in their [manifest file](/docs/creating_integration_manifest/#version). Core integrations live in the `homeassistant/components` directory, and do not need a `version` key. The architecture is the same in both cases.
:::

## The minimum

The scaffold integration contains a bit more than just the bare minimum. The minimum is that you define a `DOMAIN` constant that contains the domain of the integration. The second part is that it needs to define a setup method that returns a boolean if the set-up was successful.

Create a file `homeassistant/components/hello_state/__init__.py` with one of the two following codeblocks, depending on what you need:

- Sync component:

```python
DOMAIN = "hello_state"


def setup(hass, config):
    hass.states.set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True
```

- And if you prefer an async component:

```python
DOMAIN = "hello_state"


async def async_setup(hass, config):
    hass.states.async_set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True
```

In addition, a manifest file is required with the following keys as the bare minimum. Create `homeassistant/components/hello_state/manifest.json`.

```json
{
  "domain": "hello_state",
  "name": "Hello, state!"
}
```

To load this, add `hello_state:` to your `configuration.yaml` file. 

## What the scaffold offers

When using the scaffold script, it will go past the bare minimum of an integration. It will include a config flow, tests for the config flow and basic translation infrastructure to provide internationalization for your config flow.
