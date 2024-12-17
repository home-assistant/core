# Flexit Nordic (BACnet) integration
This integration enables control of a Flexit Nordic HVAC device from Home Assistant.

## Integration documentation
See the documentation here https://www.home-assistant.io/integrations/flexit_bacnet/

Issues can be found here https://github.com/home-assistant/core/issues?q=is%3Aissue+is%3Aopen+label%3A%22integration%3A+flexit_bacnet%22

Roadmap for the integration can be found at
https://community.home-assistant.io/t/flexit-nordic-bacnet-roadmap-ideas/675223

## flexit_bacnet
The underlying library that communicates with the device via the Bacnet protocol
can be found here https://github.com/piotrbulinski/flexit_bacnet

Device capabilities can be discovered using the bacnet_dump library found here
https://github.com/piotrbulinski/bacnet_dump

## Features
The integration allows a user to control the operation modes of the Flexit device as
well as seeing the exposed sensors and fan setpoints for the different modes.

The Flexit Go app seems to have some boundaries for setting setpoints. This table shows
how the setpoints are dependent on each other. Also for some of the setpoints, the low
value is not 0 as one would assume but is 30.


| Mode        | Setpoint | Min                   | Max                   |
|:------------|----------|:----------------------|:----------------------|
| HOME        | Supply   | AWAY Supply setpoint  | 100                   |
| HOME        | Extract  | AWAY Extract setpoint | 100                   |
| AWAY        | Supply   | 30                    | HOME Supply setpoint  |
| AWAY        | Extract  | 30                    | HOME Extract setpoint |
| HIGH        | Supply   | HOME Supply setpoint  | 100                   |
| HIGH        | Extract  | HOME Extract setpoint | 100                   |
| COOKER_HOOD | Supply   | 30                    | 100                   |
| COOKER_HOOD | Extract  | 30                    | 100                   |
| FIREPLACE   | Supply   | 30                    | 100                   |
| FIREPLACE   | Extract  | 30                    | 100                   |