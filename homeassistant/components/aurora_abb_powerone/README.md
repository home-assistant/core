# Aurora ABB PowerOne Solar Photvoltaic (PV) inverter.

This implements a direct RS485 connection to a solar inverter in the 
PVI-3.0/3.6/4.2-TL-OUTD ABB series, and may work on others.
The inverter was formerly made by PowerOne who got taken over by ABB.

The TCP/IP method of commuicating with inverters is supported by the 
python library, but not by this implementation of the homeassistant component.

The component provides a single sensor which reports the live power output
in watts.

Note the PV inverter will be unresponsive to communications when in darkness.

This is caught by the implementation which returns 'None' if there is no 
response.


### Installation

Add the following to your `configuration.yaml` file, replacing the text after 
rs485 with the serial port that your device is connected to.

```yaml
# Example configuration.yaml entry
sensor:
  # Solar PV inverter
  - platform: aurora_abb_powerone
    rs485: '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0'
```
