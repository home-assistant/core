"""
Support for the Rainforest Automation RAVEn and EMU smart meter interfaces.

For more details about the XML API used, please refer to the documentation at
https://rainforestautomation.com/wp-content/uploads/2014/02/raven_xml_api_r127.pdf
or the example API implementation at
https://github.com/rainforestautomation/Emu-Serial-API

Add to your configuration.yaml:

sensor:
    - platform: raven_emu
      device: /dev/ttyUSB0

If device is not specified, it will be auto-detected (Linux only).
"""

import datetime
import logging
import re
from xml.etree.ElementTree import XMLPullParser, ParseError

import voluptuous

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import config_validation
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt


REQUIREMENTS = ['pyserial==3.1.1']


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    voluptuous.Optional(CONF_DEVICE, default=''): config_validation.string,
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the raven/emu sensor."""
    device = config[CONF_DEVICE]
    if not device:
        # Find the USB device
        from os import listdir
        for path in listdir('/dev/serial/by-id/'):
            if path.startswith('usb-Rainforest'):
                device = '/dev/serial/by-id/%s' % path
                break
        else:
            _LOGGER.error("Could not find Rainforest serial device")
            return False

    dev = Device(device)
    add_devices([DemandSensor(dev), SummationSensor(dev), PriceSensor(dev)])


def _convert_timestamp(timestamp):
    # Timestamps are in UTC, relative to 2000-01-01
    timestamp_offset = datetime.timedelta(10957)
    utc = datetime.datetime.utcfromtimestamp(int(timestamp, 16))
    return str(dt.as_local(utc + timestamp_offset))


class Device(object):
    """Handles a Raven or Emu serial device."""

    def __init__(self, device):
        """Open the Raven or Emu and prepares for parsing."""
        from serial import Serial
        self._dev = Serial(device, 115200, timeout=0)
        self._sanitizer = re.compile(r'[^\sa-zA-Z0-9<>/_-]')
        self._init_parser()

    def _init_parser(self):
        """Reset the XML parser and primes it with a document tag."""
        self._parser = XMLPullParser(['start', 'end'])
        # Add a junk root tag so we constantly get data
        self._parser.feed("<HomeAssistant>\n")
        # Store the root tag so we can clear it to avoid amassing memory
        for (_, elem) in self._parser.read_events():
            self._root = elem
        # Reset data
        self._data = [{}]

    def update(self):
        """Pull and parse new data from the serial device."""
        try:
            serial_data = self._dev.read(1024).decode()
            self._parser.feed(self._sanitizer.sub('', serial_data))
            for (event, elem) in self._parser.read_events():
                if event == 'start':
                    self._data.append({})
                else:
                    data = self._data.pop()
                    data['text'] = elem.text
                    self._data[-1][elem.tag] = data
                if len(self._data) == 1:
                    # Clear the element from root
                    self._root.remove(elem)
        except ParseError:
            self._init_parser()

    def get(self, field):
        """Return the data accumulated for a given XML tag."""
        return self._data[0][field]

    def query_instantaneous_demand(self):
        """Request updates on instantaneous demand."""
        self._dev.write(b"<Command>\n" +
                        b"  <Name>get_instantaneous_demand</name>\n" +
                        b"  <Refresh>Y</Refresh>\n"
                        b"</Command>\n")
        self._dev.flush()

    def query_summation_delivered(self):
        """Request updates on the various summations."""
        self._dev.write(b"<Command>\n" +
                        b"  <Name>get_current_summation_delivered</name>\n" +
                        b"  <Refresh>Y</Refresh>\n" +
                        b"</Command>\n")
        self._dev.flush()

    def query_current_price(self):
        """Request updates on pricing."""
        self._dev.write(b"<Command>\n" +
                        b"  <Name>get_current_price</Name>\n" +
                        b"  <Refresh>Y</Refresh>\n" +
                        b"</Command>\n")
        self._dev.flush()


class DemandSensor(Entity):
    """Handles InstantaneousDemand blocks.

    Looks like:
    <InstantaneousDemand>
      <DeviceMacId>0x0123456789ABCDEF</DeviceMacId>
      <MeterMacId>0x0123456789ABCDEF</MeterMacId>
      <TimeStamp>0x20ba675a</TimeStamp>
      <Demand>0x0002b4</Demand>
      <Multiplier>0x00000001</Multiplier>
      <Divisor>0x000003e8</Divisor>
      <DigitsRight>0x03</DigitsRight>
      <DigitsLeft>0x0f</DigitsLeft>
      <SuppressLeadingZero>Y</SuppressLeadingZero>
    </InstantaneousDemand>
    """

    def __init__(self, dev):
        """Request to monitor instantaneous demand."""
        self._dev = dev
        self._dev.query_instantaneous_demand()
        self._data = {}

    @property
    def name(self):
        """Name of the sensor."""
        return "Energy Usage"

    @property
    def icon(self):
        """Icon to display for the sensor."""
        return 'mdi:gauge'

    @property
    def state(self):
        """Current instantaneous demand."""
        return self._data.get('demand', None)

    @property
    def device_state_attributes(self):
        """The rest of the relevant demand variables."""
        return self._data

    @property
    def unit_of_measurement(self):
        """The unit of measurement for this sensor."""
        return 'kW'

    @property
    def force_update(self):
        """Sensor may return the same data twice."""
        return True

    def update(self):
        """Collect the latest instantaneous demand state from the device."""
        self._dev.update()
        try:
            demand = self._dev.get('InstantaneousDemand')
            factor = (int(demand['Multiplier']['text'], 16)
                      / int(demand['Divisor']['text'], 16))
            digits = int(demand['DigitsRight']['text'], 16)
            self._data['timestamp'] = (
                _convert_timestamp(demand['TimeStamp']['text']))
            self._data['demand'] = (
                round(int(demand['Demand']['text'], 16) * factor, digits))
        except (KeyError, TypeError, ValueError):
            self._data = {}


class SummationSensor(Entity):
    """Handles CurrentSummationDelivered blocks.

    Looks like:
    <CurrentSummationDelivered>
      <DeviceMacId>0x0123456789ABCDEF</DeviceMacId>
      <MeterMacId>0x0123456789ABCDEF</MeterMacId>
      <TimeStamp>0x20ba8978</TimeStamp>
      <SummationDelivered>0x0000000002c5312a</SummationDelivered>
      <SummationReceived>0x0000000000000000</SummationReceived>
      <Multiplier>0x00000001</Multiplier>
      <Divisor>0x000003e8</Divisor>
      <DigitsRight>0x03</DigitsRight>
      <DigitsLeft>0x0f</DigitsLeft>
      <SuppressLeadingZero>Y</SuppressLeadingZero>
    </CurrentSummationDelivered>
    """

    def __init__(self, dev):
        """Request to monitor summation."""
        self._dev = dev
        self._dev.query_summation_delivered()
        self._data = {}

    @property
    def name(self):
        """Name of the sensor."""
        return "Energy Consumed"

    @property
    def icon(self):
        """Icon to display for the sensor."""
        return 'mdi:flash'

    @property
    def state(self):
        """Current net summation."""
        return self._data.get('summation', None)

    @property
    def device_state_attributes(self):
        """The rest of the relevant summation variables."""
        return self._data

    @property
    def unit_of_measurement(self):
        """The unit of measurement for this sensor."""
        return 'kWh'

    def update(self):
        """Collect the latest summation state from the device."""
        self._dev.update()
        try:
            summation = self._dev.get('CurrentSummationDelivered')
            factor = (int(summation['Multiplier']['text'], 16)
                      / int(summation['Divisor']['text'], 16))
            digits = int(summation['DigitsRight']['text'], 16)
            delivered = int(summation['SummationDelivered']['text'], 16)
            received = int(summation['SummationReceived']['text'], 16)
            self._data['timestamp'] = (
                _convert_timestamp(summation['TimeStamp']['text']))
            self._data['purchased'] = round(delivered * factor, digits)
            self._data['returned'] = round(received * factor, digits)
            self._data['summation'] = (
                round((delivered - received) * factor, digits))
        except (KeyError, TypeError, ValueError):
            self._data = {}


class PriceSensor(Entity):
    """Handles PriceCluster blocks.

    Looks like:
    <PriceCluster>
      <DeviceMacId>0x0123456789ABCDEF</DeviceMacId>
      <MeterMacId>0x0123456789ABCDEF</MeterMacId>
      <TimeStamp>0x20ba56b0</TimeStamp>
      <Price>0x00004e0b</Price>
      <Currency>0x0348</Currency>
      <TrailingDigits>0x05</TrailingDigits>
      <Tier>0x01</Tier>
      <StartTime>0x20b93d70</StartTime>
      <Duration>0x05a0</Duration>
      <RateLabel>Tier1</RateLabel>
    </PriceCluster>
    """

    def __init__(self, dev):
        """Request to monitor pricing."""
        self._dev = dev
        self._dev.query_current_price()
        self._data = {}

    @property
    def name(self):
        """Name of the sensor."""
        return "Energy Cost"

    @property
    def icon(self):
        """Icon to display for the sensor."""
        return 'mdi:coins'

    @property
    def state(self):
        """Current price."""
        return self._data.get('price', None)

    @property
    def device_state_attributes(self):
        """The rest of the relevant price variables."""
        return self._data

    @property
    def unit_of_measurement(self):
        """The unit of measurement for this sensor."""
        return '$/kWh'

    def update(self):
        """Collect the latest price state from the device."""
        self._dev.update()
        try:
            price = self._dev.get('PriceCluster')
            self._data['timestamp'] = (
                _convert_timestamp(price['TimeStamp']['text']))
            self._data['price'] = (
                int(price['Price']['text'], 16)
                / 10 ** int(price['TrailingDigits']['text'], 16))
            self._data['currency'] = int(price['Currency']['text'], 16)
            self._data['tier'] = int(price['Tier']['text'], 16)
            self._data['starttime'] = (
                _convert_timestamp(price['StartTime']['text']))
            duration = int(price['Duration']['text'], 16)
            self._data['duration'] = str(datetime.timedelta(minutes=duration))
            self._data['label'] = price['RateLabel']['text']
        except (KeyError, TypeError, ValueError):
            self._data = {}
