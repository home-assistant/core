---
title: "Integration with multiple platforms"
sidebar_label: Multiple platforms
---

Most integrations consist of a single platform. And in that case, it's fine to just define that one platform. However, if you are going to add a second platform, you will want to centralize your connection logic. This is done inside the component (`__init__.py`).

If your integration is configurable via `configuration.yaml`, it will cause the entry point of your configuration to change, as now users will need to set up your integration directly, and it is up to your integration to set up the platforms.

## Loading platforms when configured via a config entry

If your integration is set up via a config entry, you will need to forward the config entry to the appropriate integration to set up your platform. For more info, see the [config entry documentation](config_entries_index.md#for-platforms).

## Loading platforms when configured via configuration.yaml

If your integration is not using config entries, it will have to use our discovery helpers to set up its platforms. Note, this approach does not support unloading.

To do this, you will need to use the `load_platform` and `async_load_platform` methods from the discovery helper.

- See also a [full example that implements this logic](https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_load_platform/)
