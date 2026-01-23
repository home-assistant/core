---
title: "Integration manifest"
sidebar_label: "Manifest"
---

Every integration has a manifest file to specify its basic information. This file is stored as `manifest.json` in your integration directory. It is required to add such a file.

```json
{
  "domain": "hue",
  "name": "Philips Hue",
  "after_dependencies": ["http"],
  "codeowners": ["@balloob"],
  "dependencies": ["mqtt"],
  "documentation": "https://www.home-assistant.io/components/hue",
  "integration_type": "hub",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/balloob/hue/issues",
  "loggers": ["aiohue"],
  "requirements": ["aiohue==1.9.1"],
  "quality_scale": "platinum"
}
```

Or a minimal example that you can copy into your project:

```json
{
  "domain": "your_domain_name",
  "name": "Your Integration",
  "codeowners": [],
  "dependencies": [],
  "documentation": "https://www.example.com",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "requirements": []
}
```

## Domain

The domain is a short name consisting of characters and underscores. This domain has to be unique and cannot be changed. Example of the domain for the mobile app integration: `mobile_app`. The domain key has to match the directory this file is in.

## Name

The name of the integration.

## Version

For core integrations, this should be omitted.

The version of the integration is required for custom integrations. The version needs to be a valid version recognized by [AwesomeVersion](https://github.com/ludeeus/awesomeversion) like [CalVer](https://calver.org/) or [SemVer](https://semver.org/).

## Integration type

Integrations are split into multiple integration types. Each integration
must provide an `integration_type` in their manifest, that describes its main
focus.

:::warning
When not set, we currently default to `hub`. This default is temporary during
our transition period, every integration should set an `integration_type` and
it thus will become mandatory in the future.
:::

| Type |  Description
| ---- | -----------
| `device` | Provides a single device like, for example, ESPHome. |
| `entity` | Provides a basic entity platform, like sensor or light. This should generally not be used. |
| `hardware` | Provides a hardware integration, like Raspberry Pi or Hardkernel. This should generally not be used. |
| `helper` | Provides an entity to help the user with automations like input boolean, derivative or group. |
| `hub` | Provides a hub integration, with multiple devices or services, like Philips Hue. |
| `service` | Provides a single service, like DuckDNS or AdGuard. |
| `system` | Provides a system integration and is reserved, should generally not be used. |
| `virtual` | Not an integration on its own. Instead it points towards another integration or IoT standard. See [virtual integration](#virtual-integration) section. |

:::info
The difference between a `hub` and a `service` or `device` is defined by the nature
of the integration. A `hub` provides a gateway to multiple other devices or
services. `service` and `device` are integrations that provide a single device
or service per config entry.
:::

## Documentation

The website containing documentation on how to use your integration. If this integration is being submitted for inclusion in Home Assistant, it should be `https://www.home-assistant.io/integrations/<domain>`

## Issue tracker

The issue tracker of your integration, where users reports issues if they run into one.
If this integration is being submitted for inclusion in Home Assistant, it should be omitted. For built-in integrations, Home Assistant will automatically generate the correct link.

## Dependencies

Dependencies are other Home Assistant integrations you want Home Assistant to set up successfully before the integration is loaded. Adding an integration to dependencies will ensure the depending integration is loaded before setup, but it does not guarantee all dependency configuration entries have been set up. Adding dependencies can be necessary if you want to offer functionality from that other integration, like webhooks or an MQTT connection. Adding an [after dependency](#after-dependencies) might be a better alternative if a dependency is optional but not critical. See the [MQTT section](#mqtt) for more details on handling this for MQTT.

Built-in integrations shall only specify other built-in integrations in `dependencies`. Custom integrations may specify both built-in and custom integrations in `dependencies`.

## After dependencies

This option is used to specify dependencies that might be used by the integration but aren't essential. When `after_dependencies` is present, set up of an integration will wait for the integrations listed in `after_dependencies`, which are configured either via YAML or a config entry, to be set up first before the integration is set up. It will also make sure that the requirements of `after_dependencies` are installed so methods from the integration can be safely imported, regardless of whether the integrations listed in `after_dependencies` are configured or not. For example, if the `camera` integration might use the `stream` integration in certain configurations, adding `stream` to `after_dependencies` of `camera`'s manifest, will ensure that `stream` is loaded before `camera` if it is configured and that any dependencies of `stream` are installed and can be imported by `camera`. If `stream` is not configured, `camera` will still load.

Built-in integrations shall only specify other built-in integrations in `after_dependencies`. Custom integrations may specify both built-in and custom integrations in `after_dependencies`.

## Code owners

GitHub usernames or team names of people that are responsible for this integration. You should add at least your GitHub username here, as well as anyone who helped you to write code that is being included.

## Config flow

Specify the `config_flow` key if your integration has a config flow to create a config entry. When specified, the file `config_flow.py` needs to exist in your integration.

```json
{
  "config_flow": true
}
```

### Single config entry only

Specify the `single_config_entry` key if your integration supports only one config entry. When specified, it will not allow the user to add more than one config entry for this integration.

```json
{
  "single_config_entry": true
}
```

## Requirements

Requirements are Python libraries or modules that you would normally install using `pip` for your component. Home Assistant will try to install the requirements into the `deps` subdirectory of the Home Assistant [configuration directory](https://www.home-assistant.io/docs/configuration/) if you are not using a `venv` or in something like `path/to/venv/lib/python3.6/site-packages` if you are running in a virtual environment. This will make sure that all requirements are present at startup. If steps fail, like missing packages for the compilation of a module or other install errors, the component will fail to load.

Requirements is an array of strings. Each entry is a `pip` compatible string. For example, the media player Cast platform depends on the Python package PyChromecast v3.2.0: `["pychromecast==3.2.0"]`.

### Custom requirements during development & testing

During the development of a component, it can be useful to test against different versions of a requirement. This can be done in two steps, using `pychromecast` as an example:

```shell
pip install pychromecast==3.2.0 --target ~/.homeassistant/deps
hass --skip-pip-packages pychromecast
```

This will use the specified version, and prevent Home Assistant from trying to override it with what is specified in `requirements`. To prevent any package from being automatically overridden without specifying dependencies, you can launch Home Assistant with the global `--skip-pip` flag.

If you need to make changes to a requirement to support your component, it's also possible to install a development version of the requirement using `pip install -e`:

```shell
git clone https://github.com/balloob/pychromecast.git
pip install -e ./pychromecast
hass --skip-pip-packages pychromecast
```

It is also possible to use a public git repository to install a requirement.  This can be useful, for example, to test changes to a requirement dependency before it's been published to PyPI. Syntax:

```json
{
  "requirements": ["<library>@git+https://github.com/<user>/<project>.git@<git ref>"]
}
```
`<git ref>` can be any git reference: branch, tag, commit hash, ... . See [PIP documentation about git support](https://pip.pypa.io/en/stable/topics/vcs-support/#git).

The following example will install the `except_connect` branch of the `pycoolmaster` library directly from GitHub:

```json
{
  "requirements": ["pycoolmaster@git+https://github.com/issacg/pycoolmaster.git@except_connect"]
}
```

### Custom integration requirements

Custom integrations should only include requirements that are not required by the Core [requirements.txt](https://github.com/home-assistant/core/blob/dev/requirements.txt).

## Loggers

The `loggers` field is a list of names that the integration's requirements use for their [getLogger](https://docs.python.org/3/library/logging.html?highlight=logging#logging.getLogger) calls.

## Bluetooth

If your integration supports discovery via bluetooth, you can add a matcher to your manifest. If the user has the `bluetooth` integration loaded, it will load the `bluetooth` step of your integration's config flow when it is discovered. We support listening for Bluetooth discovery by matching on `connectable` `local_name`, `service_uuid`, `service_data_uuid`, `manufacturer_id`, and `manufacturer_data_start`. The `manufacturer_data_start` field expects a list of bytes encoded as integer values from 0-255. The manifest value is a list of matcher dictionaries. Your integration is discovered if all items of any of the specified matchers are found in the Bluetooth data. It's up to your config flow to filter out duplicates.

Matches for `local_name` may not contain any patterns in the first three (3) characters.

If the device only needs advertisement data, setting `connectable` to `false` will opt-in to receive discovery from Bluetooth controllers that do not have support for making connections.

The following example will match Nespresso Prodigio machines:

```json
{
  "bluetooth": [
    {
      "local_name": "Prodigio_*"
    }
  ]
}
```

The following example will match service data with a 128 bit uuid used for SwitchBot bot and curtain devices:

```json
{
  "bluetooth": [
    {
      "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
    }
  ]
}
```

If you want to match service data with a 16 bit uuid, you will have to convert it to a 128 bit uuid first, by replacing the 3rd and 4th byte in `00000000-0000-1000-8000-00805f9b34fb` with the 16 bit uuid. For example, for Switchbot sensor devices, the 16 bit uuid is `0xfd3d`, the corresponding 128 bit uuid becomes `0000fd3d-0000-1000-8000-00805f9b34fb`. The following example will therefore match service data with a 16 bit uuid used for SwitchBot sensor devices:

```json
{
  "bluetooth": [
    {
      "service_data_uuid": "0000fd3d-0000-1000-8000-00805f9b34fb"
    }
  ]
}
```

The following example will match HomeKit devices:


```json
{
  "bluetooth": [
    {
      "manufacturer_id": 76,
      "manufacturer_data_start": [6]
    }
  ]
}
```


## Zeroconf

If your integration supports discovery via [Zeroconf](https://en.wikipedia.org/wiki/Zero-configuration_networking), you can add the type to your manifest. If the user has the `zeroconf` integration loaded, it will load the `zeroconf` step of your integration's config flow when it is discovered.

Zeroconf is a list so you can specify multiple types to match on.

```json
{
  "zeroconf": ["_googlecast._tcp.local."]
}
```

Certain zeroconf types are very generic (i.e., `_printer._tcp.local.`, `_axis-video._tcp.local.` or `_http._tcp.local`). In such cases you should include a Name (`name`), or Properties (`properties`) filter:

```json
{
  "zeroconf": [
    {"type":"_axis-video._tcp.local.","properties":{"macaddress":"00408c*"}},
    {"type":"_axis-video._tcp.local.","name":"example*"},
    {"type":"_airplay._tcp.local.","properties":{"am":"audioaccessory*"}},
   ]
}
```

Note that all values in the `properties` filters must be lowercase, and may contain a fnmatch type wildcard.

## SSDP

If your integration supports discovery via [SSDP](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol), you can add the type to your manifest. If the user has the `ssdp` integration loaded, it will load the `ssdp` step of your integration's config flow when it is discovered. We support SSDP discovery by the SSDP ST, USN, EXT, and Server headers (header names in lowercase), as well as data in [UPnP device description](https://openconnectivity.org/developer/specifications/upnp-resources/upnp/basic-device-v1-0/). The manifest value is a list of matcher dictionaries, your integration is discovered if all items of any of the specified matchers are found in the SSDP/UPnP data. It's up to your config flow to filter out duplicates.

The following example has one matcher consisting of three items, all of which must match for discovery to happen by this config.

```json
{
  "ssdp": [
    {
      "st": "roku:ecp",
      "manufacturer": "Roku",
      "deviceType": "urn:roku-com:device:player:1-0"
    }
  ]
}
```

## HomeKit

If your integration supports discovery via HomeKit, you can add the supported model names to your manifest. If the user has the `zeroconf` integration loaded, it will load the `homekit` step of your integration's config flow when it is discovered.

HomeKit discovery works by testing if the discovered modelname starts with any of the model names specified in the manifest.json.

```json
{
  "homekit": {
    "models": [
      "LIFX"
    ]
  }
}
```

Discovery via HomeKit does not mean that you have to talk the HomeKit protocol to communicate with your device. You can communicate with the device however you see fit.

When a discovery info is routed to your integration because of this entry in your manifest, the discovery info is no longer routed to integrations that listen to the HomeKit zeroconf type.

## MQTT

If your integration supports discovery via MQTT, you can add the topics used for discovery. If the user has the `mqtt` integration loaded, it will load the `mqtt` step of your integration's config flow when it is discovered.

MQTT discovery works by subscribing to MQTT topics specified in the manifest.json.

```json
{
  "mqtt": [
    "tasmota/discovery/#"
  ]
}
```

If your integration requires `mqtt`, make sure it is added to the [dependencies](#dependencies).

Integrations depending on MQTT should wait using `await mqtt.async_wait_for_mqtt_client(hass)` for the MQTT client to become available before they can subscribe. The `async_wait_for_mqtt_client` method will block and return `True` till the MQTT client is available.

## DHCP

If your integration supports discovery via DHCP, you can add the type to your manifest. If the user has the `dhcp` integration loaded, it will load the `dhcp` step of your integration's config flow when it is discovered. We support passively listening for DHCP discovery by the `hostname` and [OUI](https://en.wikipedia.org/wiki/Organizationally_unique_identifier), or matching device registry mac address when `registered_devices` is set to `true`. The manifest value is a list of matcher dictionaries, your integration is discovered if all items of any of the specified matchers are found in the DHCP data. [Unix filename pattern matching](https://docs.python.org/3/library/fnmatch.html) is used for matching. It's up to your config flow to filter out duplicates.

If an integration wants to receive discovery flows to update the IP Address of a device when it comes
online, but a `hostname` or `oui` match would be too broad, and it has registered in the device registry with mac address using the `CONNECTION_NETWORK_MAC`,
it should add a DHCP entry with `registered_devices` set to `true`.

If the integration supports `zeroconf` or `ssdp`, these should be preferred over `dhcp` as it generally offers a better
user experience.

The following example has two matchers consisting of two items. All of the items in any of the matchers must match for discovery to happen by this config.

For example:

-  If the `hostname` was `Rachio-XYZ` and the `macaddress` was `00:9D:6B:55:12:AA`, the discovery would happen (1st matcher).
-  If the `hostname` was `Dachio-XYZ` or `Pachio-XYZ`, and the `macaddress` was `00:9D:6B:55:12:AA`, the discovery would happen (3rd matcher).
-  If the `hostname` was `Rachio-XYZ` and the `macaddress` was `00:00:00:55:12:AA`, the discovery would not happen (no matching MAC).
-  If the `hostname` was `NotRachio-XYZ` and the `macaddress` was `00:9D:6B:55:12:AA`, the discovery would not happen (no matching hostname).


```json
{
  "dhcp": [
    {
    "hostname": "rachio-*",
    "macaddress": "009D6B*"
    },
    {
    "hostname": "[dp]achio-*",
    "macaddress": "009D6B*"
    }
  ]
}
```

Example with setting `registered_devices` to `true`:

```json
{
  "dhcp": [
    {
    "hostname": "myintegration-*",
    },
    {
    "registered_devices": true,
    }
  ]
}
```

## USB

If your integration supports discovery via usb, you can add the type to your manifest. If the user has the `usb` integration loaded, it will load the `usb` step of your integration's config flow when it is discovered. We support discovery by VID (Vendor ID), PID (Device ID), Serial Number, Manufacturer, and Description by extracting these values from the USB descriptor. For help identifying these values see [How To Identify A Device](https://wiki.debian.org/HowToIdentifyADevice/USB). The manifest value is a list of matcher dictionaries. Your integration is discovered if all items of any of the specified matchers are found in the USB data. It's up to your config flow to filter out duplicates.

:::warning
Some VID and PID combinations are used by many unrelated devices. For example VID `10C4` and PID `EA60` matches any Silicon Labs CP2102 USB-Serial bridge chip. When matching these type of devices, it is important to match on `description` or another identifier to avoid an unexpected discovery.
:::

The following example has two matchers consisting of two items. All of the items in any of the two matchers must match for discovery to happen by this config.

For example:

-  If the `vid` was `AAAA` and the `pid` was `AAAA`, the discovery would happen.
-  If the `vid` was `AAAA` and the `pid` was `FFFF`, the discovery would not happen.
-  If the `vid` was `CCCC` and the `pid` was `AAAA`, the discovery would not happen.
-  If the `vid` was `1234`, the `pid` was `ABCD`, the `serial_number` was `12345678`, the `manufacturer` was `Midway USB`, and the `description` was `Version 12 Zigbee Stick`, the discovery would happen.

```json
{
  "usb": [
    {
    "vid": "AAAA",
    "pid": "AAAA"
    },
    {
    "vid": "BBBB",
    "pid": "BBBB"
    },
    {
    "vid": "1234",
    "pid": "ABCD",
    "serial_number": "1234*",
    "manufacturer": "*midway*",
    "description": "*zigbee*"
    },
  ]
}
```

## Integration quality scale

The [Integration Quality Scale](/docs/core/integration-quality-scale) scores an integration on the code quality and user experience. Each level of the quality scale consists of a list of requirements. If an integration matches all requirements, it's considered to have reached that level.

New integrations are required to fulfill at least the bronze tier so be sure to look at the [Integration Quality Scale](/docs/core/integration-quality-scale) list of requirements. It helps to improve the code and user experience tremendously.

```json
{
 "quality_scale": "silver"
}
```

## IoT class

The [IoT class][iot_class] describes how an integration connects with, e.g., a device or service. For more information
about IoT Classes, read the blog about ["Classifying the Internet of Things"][iot_class].

The following IoT classes are accepted in the manifest:

- `assumed_state`: We are unable to get the state of the device. Best we can do is to assume the state based on our last command.
- `cloud_polling`: The integration of this device happens via the cloud and requires an active internet connection. Polling the state means that an update might be noticed later.
- `cloud_push`: Integration of this device happens via the cloud and requires an active internet connection. Home Assistant will be notified as soon as a new state is available.
- `local_polling`: Offers direct communication with device. Polling the state means that an update might be noticed later.
- `local_push`: Offers direct communication with device. Home Assistant will be notified as soon as a new state is available.
- `calculated`: The integration does not handle communication on its own, but provides a calculated result.

[iot_class]: https://www.home-assistant.io/blog/2016/02/12/classifying-the-internet-of-things/#classifiers

## Virtual integration

Some products are supported by integrations that are not named after the product. For example, Yale Home locks are integrated via the August integration, and the IKEA SYMFONISK product line can be used with the Sonos integration.

There are also cases where a product line only supports a standard IoT standards like Zigbee or Z-Wave. For example, the U-tec ultraloq works via Z-Wave and has no specific dedicated integration. 

For end-users, it can be confusing to find how to integrate those products with Home Asssistant. To help with these above cases, Home Assistant has "Virtual integrations". These integrations are not real integrations but are used to help users find the right integration for their device.

A virtual integration is an integration that just has a single manifest file, without any additional code. There are two types of virtual integrations: A virtual integration supported by another integration and one that uses an existing IoT standard.

:::info
Virtual integrations can only be provided by Home Assistant Core and not by custom integrations.
:::

### Supported by

The "Supported by" virtual integration is an integration that points to another integration to provide its implementation. For example, Yale Home locks are integrated via the August (`august`) integration.

Example manifest:

```json
{
  "domain": "yale_home",
  "name": "Yale Home",
  "integration_type": "virtual",
  "supported_by": "august"
}
```

The `domain` and `name` are the same as with any other integration, but the `integration_type` is set to `virtual`. 
The logo for the domain of this virtual integration must be added to our [brands repository](https://github.com/home-assistant/brands/), so in this case, a Yale Home branding is used.

The `supported_by` is the domain of the integration providing the implementation for this product. In the example above, the Yale Home lock is supported by the August integration and points to its domain `august`.

Result:

- Yale Home is listed on our user documentation website under integrations with an automatically generated stub page that directs the user to the integration to use.
- Yale Home is listed in Home Assistant when clicking "add integration". When selected, we explain to the user that this product is integrated using a different integration, then the user continues to the Xioami Miio config flow.

### IoT standards

The "IoT Standards" virtual integration is an integration that uses an existing IoT standard to provide connectivity with the device. For example, the U-tec ultraloq works via Z-Wave and has no specific dedicated integration.

Example manifest:

```json
{
  "domain": "ultraloq",
  "name": "ultraloq",
  "integration_type": "virtual",
  "iot_standards": ["zwave"],
}

```

The `domain` and `name` are the same as with any other integration, but the `integration_type` is set to `virtual`. 
The logo for the domain of this virtual integration should be added to our [brands repository](https://github.com/home-assistant/brands/).

The `iot_standards` is the standard this product uses for connectivity. In the example above, the U-tech ultraloq products use Z-Wave to integrate with Home Assistant.

Result:

- U-tech ultraloq is listed on our user documentation website under integrations with an automatically generated stub page that directs the user to the integration to use.
- U-tech ultraloq is listed in Home Assistant when clicking "add integration". When selected, we guide the user in adding this Z-Wave device (and in case Z-Wave isn't set up yet, into setting up Z-Wave first).

:::info
Brands also [support setting IoT standards](/docs/creating_integration_brand/#iot-standards).

It is preferred to set IoT standards on the brand level, and only use a virtual
integration in case it would impose confusion for the end user.
:::
