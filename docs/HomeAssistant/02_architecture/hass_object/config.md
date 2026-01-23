---
title: "Config"
---

On [the hass object](./dev_101_hass.md) there is an instance of the Config class. The Config class contains the users preferred units, the path to the config directory and which components are loaded.

| Name | Type | Description |
| ---- | ---- | ----------- |
| latitude | float | Latitude of the instance location |
| longitude | float | Longitude of the instance location |
| elevation | int | Elevation of the instance |
| location_name | str | Name of the instance |
| time_zone | str | Timezone |
| units | UnitSystem | Unit system |
| internal_url | str | URL the instance can be reached on internally |
| external_url | str | URL the instance can be reached on externally |
| currency | str | Preferred currency |
| country | str | Country the instance is in |
| language | str | Preferred language |
| config_source | ConfigSource | If the configuration was set via the UI or stored in YAML |
| skip_pip | bool | If True, pip install is skipped for requirements on startup |
| skip_pip_packages | list[str] | List of packages to skip when installing requirements on startup |
| components | set[str] | List of loaded components |
| api | ApiConfig | API (HTTP) server configuration |
| config_dir | str | Directory that holds the configuration |
| allowlist_external_dirs | set[str] | List of allowed external dirs to access |
| allowlist_external_urls | set[str] | List of allowed external URLs that integrations may use |
| media_dirs | dict[str, str] | Dictionary of Media folders that integrations may use |
| safe_mode | bool | If Home Assistant is running in safe mode |
| legacy_templates | bool | Use legacy template behavior |

It also provides some helper methods.
