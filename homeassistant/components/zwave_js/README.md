# Z-Wave JS Architecture

This document describes the architecture of Z-Wave JS in Home Assistant and how the integration is connected all the way to the Z-Wave USB stick controller.

## Architecture

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

#### Z-Wave JS integration

Represents Z-Wave devices in Home Assistant and allows control.

#### Home Assistant

Best home automation platform in the world.

### Running Z-Wave JS Server

![alt text][running_zwave_js_server]

Z-Wave JS Server can be run as a standalone Node app.

It can also run as part of Z-Wave JS 2 MQTT, which is also a standalone Node app.

Both apps are available as Home Assistant add-ons. There are also Docker containers etc.

[connection_diagram]: docs/z_wave_js_connection.png "Connection Diagram"
[//]: # (https://docs.google.com/drawings/d/10yrczSRwV4kjQwzDnCLGoAJkePaB0BMVb1sWZeeDO7U/edit?usp=sharing)

[running_zwave_js_server]: docs/running_z_wave_js_server.png "Running Z-Wave JS Server"
[//]: # (https://docs.google.com/drawings/d/1YhSVNuss3fa1VFTKQLaACxXg7y6qo742n2oYpdLRs7E/edit?usp=sharing)
