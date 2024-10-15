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

## Adding new entities

All feature-based entities are created based on the information from the upstream library.
If you want to add new feature, it needs to be implemented at first in there.
After the feature is exposed by the upstream library,
it needs to be added to the `<PLATFORM>_DESCRIPTIONS` list of the corresponding platform.
The integration logs missing descriptions on features supported by the device to help spotting them.

In many cases it is enough to define the `key` (corresponding to upstream `feature.id`),
but you can pass more information for nicer user experience:
* `device_class` and `state_class` should be set accordingly for binary_sensor and sensor
* If no matching classes are available, you need to update `strings.json` and `icons.json`
When doing so, do not forget to run `script/setup` to generate the translations.

Other information like the category and whether to enable per default are read from the feature,
as are information about units and display precision hints.

