---
title: "Checklist for creating a platform"
sidebar_label: Platform checklist
---

A checklist of things to do when you're adding a new platform.

:::info
Not all existing platforms follow the requirements in this checklist. This cannot be used as a reason to not follow them!
:::

### 0. Common

1. Follow our [Style guidelines](development_guidelines.md)
2. Use existing constants from [`const.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/const.py)
   - Only add new constants to `const.py` if they are widely used. Otherwise keep them on platform level
   - Use `CONF_MONITORED_CONDITIONS` instead of `CONF_MONITORED_VARIABLES`

### 1. External requirements

1. Requirements have been added to [`manifest.json`](creating_integration_manifest.md). The `REQUIREMENTS` constant is deprecated.
2. Requirement version should be pinned: `"requirements": ['phue==0.8.1']`
3. We no longer want requirements hosted on GitHub. Please upload to PyPi.
4. Each requirement meets the [library requirements](api_lib_index.md#basic-library-requirements).

### 2. Configuration

1. If the platform can be set up directly, add a voluptuous schema for [configuration validation](development_validation.md)
2. Voluptuous schema extends schema from component  
   (e.g., `hue.light.PLATFORM_SCHEMA` extends `light.PLATFORM_SCHEMA`)
3. Default parameters specified in voluptuous schema, not in `setup_platform(...)`
4. Your `PLATFORM_SCHEMA` should use as many generic config keys as possible from `homeassistant.const`
5. Never depend on users adding things to `customize` to configure behavior inside your platform.

```python
import voluptuous as vol

from homeassistant.const import CONF_FILENAME, CONF_HOST
from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

CONF_ALLOW_UNREACHABLE = "allow_unreachable"
DEFAULT_UNREACHABLE = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_ALLOW_UNREACHABLE, default=DEFAULT_UNREACHABLE): cv.boolean,
        vol.Optional(CONF_FILENAME): cv.string,
    }
)
```

### 3. Setup platform

1. Verify that the passed in configuration (user/pass/host etc.) works.
2. Group your calls to `add_entities if possible.
3. If the platform adds extra actions, the format should be `<domain of your integration>.<service action name>`. So if your integration's domain is "awesome_sauce" and you are making a light platform, you would register service actions under the `awesome_sauce` domain. Make sure that your service actions [verify permissions](auth_permissions.md#checking-permissions).

### 4. Entity

1. Extend the entity from the integration you're building a platform for.

    ```python
    from homeassistant.components.light import Light
    
    
    class HueLight(Light):
        """Hue light component."""
    ```

2. Avoid passing in `hass` as a parameter to the entity. `hass` will be set on the entity when the entity is added to Home Assistant. This means you can access `hass` as `self.hass` inside the entity.
3. Do not call `update()` in constructor, use `add_entities(devices, update_before_add=True)` instead.
4. Do not do any I/O inside properties. Cache values inside `update()` instead.
5. When dealing with time, state and/or attributes should not contain relative time since something happened. Instead, it should store UTC timestamps.
6. Leverage the [entity lifecycle callbacks](core/entity.md#lifecycle-hooks) to attach event listeners or clean up connections.

### 5. Communication with devices/services

1. All API specific code has to be part of a third party library hosted on PyPi. Home Assistant should only interact with objects and not make direct calls to the API.

    ```python
    # bad
    status = requests.get(url("/status"))
    # good
    from phue import Bridge

    bridge = Bridge(...)
    status = bridge.status()
    ```

    [Tutorial on publishing your own PyPI package](https://towardsdatascience.com/how-to-open-source-your-first-python-package-e717444e1da0)

    Other noteworthy resources for publishing python packages:  
    [Cookiecutter Project](https://cookiecutter.readthedocs.io/)  
    [flit](https://flit.readthedocs.io/)  
    [Poetry](https://python-poetry.org/)  
