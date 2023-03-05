# Z-Wave Integration

This document covers details that new contributors may find helpful when getting started.

## Improving device support

This section can help new contributors learn how to improve Z-Wave device support within Home Assistant.

The Z-Wave integration uses a discovery mechanism to create the necessary entities for each of your Z-Wave nodes. To perform this discovery, the integration iterates through each node's [Values](https://zwave-js.github.io/node-zwave-js/#/api/valueid) and compares them to a list of [discovery rules](./discovery.py). If there is a match between a particular discovery rule and the given Value, the integration creates an entity for that value using information sent from the discovery logic to indicate entity platform and instance type.

In cases where an entity's functionality requires interaction with multiple Values, the discovery rule for that particular entity type is based on the primary Value, or the Value that must be there to indicate that this entity needs to be created, and then the rest of the Values required are discovered by the class instance for that entity. A good example of this is the discovery logic for the `climate` entity. Currently, the discovery logic is tied to the discovery of a Value with a property of `mode` and a command class of `Thermostat Mode`, but the actual entity uses many more Values than that to be fully functional as evident in the [code](./climate.py).

There are several ways that device support can be improved within Home Assistant, but regardless of the reason, it is important to add device specific tests in these use cases. To do so, add the device's data (from device diagnostics) to the [fixtures folder](../../../tests/components/zwave_js/fixtures) and then define the new fixtures in [conftest.py](../../../tests/components/zwave_js/conftest.py). Use existing tests as the model but the tests can go in the [test_discovery.py module](../../../tests/components/zwave_js/test_discovery.py).

### Switching HA support for a device from one entity type to another.

Sometimes manufacturers don't follow the spec properly and implement functionality using the wrong command class, resulting in HA discovering the feature as the wrong entity type. There is a section in the [discovery rules](./discovery.py) for device specific discovery. This can be used to override the type of entity that HA discovers for that particular device's primary Value.

### Adding feature support to complex entity types

Sometimes the generic Z-Wave entity logic does not provide all of the features a device is capable of. A great example of this is a climate entity where the current temperature is determined by one of multiple sensors that is configurable by a configuration parameter. In these cases, there is a section in the [discovery rules](./discovery.py) for device specific discovery. By leveraging [discovery_data_template.py](./discovery_data_template.py), it is possible to create the same entity type but with different logic. Generally, we don't like to create entity classes that are device specific, so this mechanism allows us to generalize the implementation.

## Architecture

This section describes the architecture of Z-Wave JS in Home Assistant and how the integration is connected all the way to the Z-Wave USB stick controller.

### Connection diagram

![alt text][connection_diagram]

#### Z-Wave USB stick

Communicates with devices via the Z-Wave radio and stores device pairing.

#### Z-Wave JS

Represents the USB stick serial protocol as devices.

#### Z-Wave JS Server

Forward the state of Z-Wave JS over a WebSocket connection.

#### Z-Wave JS Server Python

Consumes the WebSocket connection and makes the Z-Wave JS state available in Python.

#### Z-Wave integration

Represents Z-Wave devices in Home Assistant and allows control.

#### Home Assistant

Best home automation platform in the world.

### Running Z-Wave JS Server

![alt text][running_zwave_js_server]

Z-Wave JS Server can be run as a standalone Node app.

It can also run as part of Z-Wave JS UI, which is also a standalone Node app.

Both apps are available as Home Assistant add-ons. There are also Docker containers etc.

[connection_diagram]: docs/z_wave_js_connection.png "Connection Diagram"
[//]: # (https://docs.google.com/drawings/d/10yrczSRwV4kjQwzDnCLGoAJkePaB0BMVb1sWZeeDO7U/edit?usp=sharing)

[running_zwave_js_server]: docs/running_z_wave_js_server.png "Running Z-Wave JS Server"
[//]: # (https://docs.google.com/drawings/d/1YhSVNuss3fa1VFTKQLaACxXg7y6qo742n2oYpdLRs7E/edit?usp=sharing)
