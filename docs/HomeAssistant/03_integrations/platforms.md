---
title: "Integration platforms"
sidebar_label: "Platforms"
---

Home Assistant has various built-in integrations that abstract device types. There are [lights](core/entity/light.md), [switches](core/entity/switch.md), [covers](core/entity/cover.md), [climate devices](core/entity/climate.md), and [many more](core/entity.md). Your integration can hook into these integrations by creating a platform. You will need a platform for each integration that you are integrating with.

To create a platform, you will need to create a file with the domain name of the integration that you are building a platform for. So if you are building a light, you will add a new file `light.py` to your integration folder.

We have created two example integrations that should give you a look at how this works:

- [Example sensor platform](https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_sensor/): hello world of platforms.
- [Example light platform](https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_light/): showing best practices.

### Interfacing with devices

One Home Assistant rule is that the integration should never interface directly with devices. Instead, it should interact with a third-party Python 3 library. This way, Home Assistant can share code with the Python community and keep the project maintainable.

Once you have your Python library [ready and published to PyPI](api_lib_index.md), add it to the [manifest](creating_integration_manifest.md). It will now be time to implement the Entity base class that is provided by the integration that you are creating a platform for.

Find your integration at the [entity index](core/entity.md) to see what methods and properties are available to implement.
