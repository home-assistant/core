# TPLink Integration

This document covers details that new contributors may find helpful when getting started.

## Modules vs Features

The kasa library which this integration depends on exposes functionality via modules and features.
The `Module` apis encapsulate groups of functionality provided by a device,
e.g. Light which has multiple attributes and methods such as `set_has`, `brightness` etc.
The `features` encapsulate unitary functions and allow for introspection.
e.g. `on_since`, `voltage` etc.

If the integration implements a platform that presents single functions or data points, such as `sensor`,
`button`, `switch` it uses features.
If it's implementing a platform with more complex functionality like `light`, `fan` or `climate` it will
use modules.

## Dynamic feature creation

Entities can be dynamically created by inspecting various properties of a feature such
as `type`, `unit` or `precision`. If more data is needed than the feature provides,
i.e. to set HA `device_class` or `state_class` on a sensor entity, then a static `EntityExtras` entry
should be created in `const.py`.

### Translation keys and icons

For `Feature` based platforms translation keys should match `feature.id`.
If a translation key and icon has been added to `strings.json` and `icons.json` it should be added to
`ENTITY_EXTRAS` as an indication not to set the `name` or `icon` from the feature,
as it will override the translation otherwise.

