# TPLink Integration

This document covers details that new contributors may find helpful when getting started.

## Modules vs Features

The python-kasa library which this integration depends on exposes functionality via modules and features.
The `Module` APIs encapsulate groups of functionality provided by a device,
e.g. Light which has multiple attributes and methods such as `set_hsv`, `brightness` etc.
The `features` encapsulate unitary functions and allow for introspection.
e.g. `on_since`, `voltage` etc.

If the integration implements a platform that presents single functions or data points, such as `sensor`,
`button`, `switch` it uses features.
If it's implementing a platform with more complex functionality like `light`, `fan` or `climate` it will
use modules.

## Dynamic feature creation

Entity attributes are dynamically set by inspecting various properties of a feature such
as `type`, `unit` or `precision`.
If more data is needed than the feature provides,
i.e. to set HA `device_class` or `state_class` on a sensor entity, then add it to the static
`PLATFORM_DESCRIPTIONS` entry in the appropriate platform.
All feature ids should be described in the static entity descriptions but if a new feature
is not yet added it will be created manually and a warning will be logged.

### Translation keys and icons

For features to use translation keys they should be added to `strings.json` and `icons.json`
with the feature.id as key.

**All described features must have corresponding entries in `strings.json` and `icons.json`
unless the base platform provides it's own via the device_class**

