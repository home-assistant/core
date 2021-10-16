# Serial-BenQ-Projector-Home-Assistant-Integration
A Custom Integration for Home Assistant to integrate a BenQ Projector on it!

```# Example configuration.yaml entry
switch:
    - platform: benq_projector
      filename: /dev/ttyUSB0
```
    
# Settings

filename (string, Required)
The pipe where the projector is connected to.

baudrate (integer, Optional)
Speed of the serial connection (Default is 115200)

name (string, Optional)
The name to use when displaying this switch.

timeout (integer, Optional)
Timeout for the connection in seconds.

write_timeout (integer, Optional)
Write timeout in seconds.
