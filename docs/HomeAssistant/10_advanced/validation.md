---
title: "Validate the input"
---

The `configuration.yaml` file contains the configuration options for components and platforms. We use [voluptuous](https://pypi.python.org/pypi/voluptuous) to make sure that the configuration provided by the user is valid. Some entries are optional or could be required to set up a platform or a component. Others must be a defined type or from an already-defined list.

We test the configuration to ensure that users have a great experience and minimize notifications if something is wrong with a platform or component setup before Home Assistant runs.

Besides [voluptuous](https://pypi.python.org/pypi/voluptuous) default types, many custom types are available. For an overview, take a look at the [config_validation.py](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/config_validation.py) helper.

- Types: `string`, `byte`, and `boolean`
- Entity ID: `entity_id` and `entity_ids`
- Numbers: `small_float` and `positive_int`
- Time: `time`, `time_zone`
- Misc: `template`, `slug`, `temperature_unit`, `latitude`, `longitude`, `isfile`, `sun_event`, `ensure_list`, `port`, `url`,  and `icon`

To validate platforms using [MQTT](https://www.home-assistant.io/components/mqtt/), `valid_subscribe_topic` and `valid_publish_topic` are available.

Some things to keep in mind:

- Use the constants defined in `const.py`
- Import `PLATFORM_SCHEMA` from the integration you are integrating with and extend it.
- Preferred order is `required` first and `optional` second
- Default values for optional configuration keys need to be valid values. Don't use a default which is `None` like `vol.Optional(CONF_SOMETHING, default=None): cv.string`, set the default to `default=''` if required.

### Snippets

This section contains snippets for the validation we use.

#### Default name

It's common to set a default for a sensor if the user doesn't provide a name to use.

```python
DEFAULT_NAME = "Sensor name"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # ...
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)
```

#### Limit the values

You might want to limit the user's input to a couple of options.

```python
DEFAULT_METHOD = "GET"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # ...
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(["POST", "GET"]),
    }
)
```

#### Port

All port numbers are from a range of 1 to 65535.

```python
DEFAULT_PORT = 993

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # ...
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)
```

#### Lists

If a sensor has a pre-defined list of available options, test to make sure the configuration entry matches the list.

```python
SENSOR_TYPES = {
    "article_cache": ("Article Cache", "MB"),
    "average_download_rate": ("Average Speed", "MB/s"),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # ...
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)
```
