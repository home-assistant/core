"""
homeassistant.components.light.lifx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
LiFX platform that implements lights

Configuration:

light:
  # platform name
  platform: lifx
  # optional server address
  # only needed if using more than one network interface
  # (omit if you are unsure)
  server: 192.168.1.3
  # optional broadcast address, set to reach all LiFX bulbs
  # (omit if you are unsure)
  broadcast: 192.168.1.255

"""
# pylint: disable=missing-docstring

import logging
import threading
import time
import queue
import socket
import io
import struct
import ipaddress
import colorsys

from struct import pack
from enum import IntEnum
from homeassistant.helpers.event import track_time_change
from homeassistant.components.light import \
    (Light, ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []
REQUIREMENTS = []

CONF_SERVER = "server"        # server address configuration item
CONF_BROADCAST = "broadcast"  # broadcast address configuration item
RETRIES = 10                  # number of packet send retries
DELAY = 0.05                  # delay between retries
UDP_PORT = 56700              # udp port for listening socket
UDP_IP = "0.0.0.0"            # address for listening socket
MAX_ACK_AGE = 1               # maximum ACK age in seconds
BUFFERSIZE = 1024             # socket buffer size
SHORT_MAX = 65535             # short int maximum
BYTE_MAX = 255                # byte maximum
SEQUENCE_BASE = 1             # packet sequence base
SEQUENCE_COUNT = 255          # packet sequence count

HUE_MIN = 0
HUE_MAX = 360
SATURATION_MIN = 0
SATURATION_MAX = 255
BRIGHTNESS_MIN = 0
BRIGHTNESS_MAX = 65535
TEMP_MIN = 2500
TEMP_MAX = 9000
TEMP_MIN_HASS = 154
TEMP_MAX_HASS = 500


class PayloadType(IntEnum):
    """ LIFX message payload types. """
    GETSERVICE = 2
    STATESERVICE = 3
    GETHOSTINFO = 12
    STATEHOSTINFO = 13
    GETHOSTFIRMWARE = 14
    STATEHOSTFIRMWARE = 15
    GETWIFIINFO = 16
    STATEWIFIINFO = 17
    GETWIFIFIRMWARE = 18
    STATEWIFIFIRMWARE = 19
    GETPOWER1 = 20
    SETPOWER1 = 21
    STATEPOWER1 = 22
    GETLABEL = 23
    SETLABEL = 24
    STATELABEL = 25
    GETVERSION = 32
    STATEVERSION = 33
    GETINFO = 34
    STATEINFO = 35
    ACKNOWLEDGEMENT = 45
    GETLOCATION = 48
    STATELOCATION = 50
    GETGROUP = 51
    STATEGROUP = 53
    ECHOREQUEST = 58
    ECHORESPONSE = 59
    GET = 101
    SETCOLOR = 102
    STATE = 107
    GETPOWER2 = 116
    SETPOWER2 = 117
    STATEPOWER2 = 118


class Power(IntEnum):
    """ LIFX power settings. """
    BULB_ON = 65535
    BULB_OFF = 0


def gen_header(sequence, payloadtype):
    """ Create LIFX packet header. """
    protocol = bytearray.fromhex("00 34")
    source = bytearray.fromhex("42 52 4b 52")
    target = bytearray.fromhex("00 00 00 00 00 00 00 00")
    reserved1 = bytearray.fromhex("00 00 00 00 00 00")
    sequence = pack("<B", sequence)
    ack = pack(">B", 3)
    reserved2 = bytearray.fromhex("00 00 00 00 00 00 00 00")
    packet_type = pack("<H", payloadtype)
    reserved3 = bytearray.fromhex("00 00")

    # assemble header
    header = bytearray(protocol)
    header.extend(source)
    header.extend(target)
    header.extend(reserved1)
    header.extend(ack)
    header.extend(sequence)
    header.extend(reserved2)
    header.extend(packet_type)
    header.extend(reserved3)

    return header


def gen_packet(sequence, payloadtype, payload=None):
    """ Generate LIFX packet header. """
    contents = gen_header(sequence, payloadtype)

    # add payload
    if payload:
        contents.extend(payload)

    # get packet size
    size = pack("<H", len(contents) << 1)

    # assemble complete packet
    packet = bytearray(size)
    packet.extend(contents)

    return packet


def gen_payload_setcolor(sequence, hue, sat, bri, kel):
    """ Generate LIFX "setcolor" packet payload. """
    hue = min(max(hue, HUE_MIN), HUE_MAX)
    sat = min(max(sat, SATURATION_MIN), SATURATION_MAX)
    bri = min(max(bri, BRIGHTNESS_MIN), BRIGHTNESS_MAX)
    kel = min(max(kel, TEMP_MIN), TEMP_MAX)

    reserved1 = pack("<B", 0)
    hue = pack("<H", int(SHORT_MAX * hue / HUE_MAX))
    saturation = pack("<H", int(SHORT_MAX * sat / SATURATION_MAX))
    brightness = pack("<H", bri)
    kelvin = pack("<H", kel)
    reserved2 = pack("<L", 0)

    payload = bytearray(reserved1)
    payload.extend(hue)
    payload.extend(saturation)
    payload.extend(brightness)
    payload.extend(kelvin)
    payload.extend(reserved2)

    return gen_packet(sequence, PayloadType.SETCOLOR, payload)


def gen_payload_get(sequence):
    """ Generate LIFX "get" packet payload. """
    # generate payload for Get message
    return gen_packet(sequence, PayloadType.GET)


def gen_payload_setpower(sequence, power):
    """ Generate LIFX "setpower" packet payload. """
    level = pack("<H", Power.BULB_OFF if power == 0 else Power.BULB_ON)
    duration = pack("<L", 0)

    payload = bytearray(level)
    payload.extend(duration)

    return gen_packet(sequence, PayloadType.SETPOWER2, payload)


# pylint: disable=too-many-locals,too-many-statements,too-many-branches
def packet_listener(data, add_device_callback):
    """ LIFX packet listener. """

    # start with no devices
    devices = []

    addr = data.server_addr

    while True:
        datastream, source = data.sock.recvfrom(BUFFERSIZE)
        ipaddr, port = source

        try:
            sio = io.BytesIO(datastream)

            dummy1, sec_part = struct.unpack("<HH", sio.read(4))

            protocol = sec_part % 4096

            if protocol == 1024:
                source, dummy1, dummy2, dummy3, sequence, dummy4, \
                    payloadtype, dummy5 = struct.unpack("<IQ6sBBQHH",
                                                        sio.read(32))

                # have we seen this ip before?
                bulb = None
                for device in devices:
                    if device.ipaddr == ipaddr:
                        bulb = device
                        break

                src = ipaddr if bulb is None else bulb.name

                if ipaddr == addr:
                    # broadcast packet
                    continue

                _LOGGER.debug("rx [%s] type [%d] sequence [%d]", ipaddr,
                              payloadtype, sequence)

                # haven't seen this ip address before and it's not a STATE
                # message (which is our key to add a new bulb)
                if bulb is None and payloadtype != PayloadType.STATE:
                    _LOGGER.debug("[%s] [%d] checking for new bulb", src, type)
                    data.probe(ipaddr)

                elif payloadtype == PayloadType.ACKNOWLEDGEMENT:
                    data.acks[sequence] = time.time()
                    _LOGGER.debug("[%s] ACK %d", src, sequence)

                elif payloadtype == PayloadType.STATESERVICE:
                    serv, port = struct.unpack("<BI", sio.read(5))
                    _LOGGER.debug("[%s] StateService [%d %d]", src, serv, port)

                elif payloadtype == PayloadType.STATEHOSTINFO:
                    sig, _tx, _rx, res = struct.unpack("<fIIh", sio.read(14))
                    _LOGGER.debug("[%s] StateHostInfo [%f %d %d %d]",
                                  src, sig, _tx, _rx, res)

                elif payloadtype == PayloadType.STATEHOSTFIRMWARE:
                    build, res, ver = struct.unpack("<QQI", sio.read(20))
                    _LOGGER.debug("[%s] StateHostFirmware [%d %d %d]",
                                  src, build, res, ver)

                elif payloadtype == PayloadType.STATEWIFIINFO:
                    sig, _tx, _rx, res = struct.unpack("<fIIh", sio.read(16))
                    _LOGGER.debug("[%s] StateWifiInfo [%f %d %d %d]",
                                  src, sig, _tx, _rx, res)

                elif payloadtype == PayloadType.STATEWIFIFIRMWARE:
                    build, _reserved, ver = struct.unpack("<QQI", sio.read(20))
                    _LOGGER.debug("[%s] StateWifiFirmware [%d %d %d]",
                                  src, build, _reserved, ver)

                elif payloadtype == PayloadType.STATEPOWER1:
                    level, = struct.unpack("<H", sio.read(2))
                    _LOGGER.debug("[%s] StatePower1 [%s]",
                                  src,
                                  "off" if level == Power.BULB_OFF else "on")

                elif payloadtype == PayloadType.STATELABEL:
                    label, = struct.unpack("<32s", sio.read(32))
                    name = label.decode('ascii')
                    name = name.replace('\x00', '')
                    _LOGGER.debug("[%s] StateLabel [\"%s\"]", src, name)

                elif payloadtype == PayloadType.STATEVERSION:
                    ven, prod, ver = struct.unpack("<HHH", sio.read(12))
                    _LOGGER.debug("[%s] StateVersion [%d %d %d]",
                                  src, ven, prod, ver)

                elif payloadtype == PayloadType.STATEINFO:
                    _tm, uptm, dwntm = struct.unpack("<QQQ", sio.read(24))
                    _LOGGER.debug("[%s] StateInfo [%d %d %d]",
                                  src, _tm, uptm, dwntm)

                elif payloadtype == PayloadType.STATELOCATION:
                    loc, label, upd = struct.unpack("<10s32sQ", sio.read(50))
                    _LOGGER.debug("[%s] StateLocation [%s %s %d]",
                                  src, loc, label, upd)

                elif payloadtype == PayloadType.STATEGROUP:
                    grp, label, upd = struct.unpack("<16s32sQ", sio.read(56))
                    _LOGGER.debug("[%s] StateGroup [%s %s %d]",
                                  src, grp, label, upd)

                elif payloadtype == PayloadType.ECHORESPONSE:
                    dummy1, = struct.unpack("<64s", sio.read(64))
                    _LOGGER.debug("[%s] EchoResponse", src)

                elif payloadtype == PayloadType.STATE:
                    hue, sat, bri, kel, dummy1, power, label, dummy2 = \
                        struct.unpack("<HHHHhH32sQ", sio.read(52))
                    name = label.decode('ascii')
                    name = name.replace('\x00', '')
                    _LOGGER.debug("[%s] State [%s %d %d %d %s \"%s\"]",
                                  src, hue, sat, bri, kel,
                                  "off" if power == Power.BULB_OFF else "on",
                                  name)

                    scaled_hue = int(HUE_MAX * hue / SHORT_MAX)
                    scaled_sat = int(SATURATION_MAX * sat / SHORT_MAX)

                    if bulb is None:
                        # bulb does not exist, create new one
                        _LOGGER.info("[%s] added to device list", name)
                        bulb = LIFXLight(data, ipaddr, name, power,
                                         scaled_hue, scaled_sat, bri, kel)
                        devices.append(bulb)
                        add_device_callback([bulb])
                    else:
                        # bulb exists so update settings
                        bulb.set_power(power)
                        bulb.set_color(scaled_hue, scaled_sat, bri, kel)
                        bulb.update_ha_state()

                elif payloadtype == PayloadType.STATEPOWER2:
                    level, = struct.unpack("<H", sio.read(2))
                    _LOGGER.debug("[%s] StatePower2 [%d]", src, level)

            else:
                _LOGGER.warning("Not LIFX packet")

        # pylint: disable=broad-except
        except Exception as exc:
            _LOGGER.error("Unable to process packet [%s]", exc)


class LIFXData():
    """ Provides LIFX data. """
    def __init__(self, config):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._acks = [0.0 for _ in range(SEQUENCE_COUNT)]
        self._seq = {"lock": threading.Lock(), "sequence": -1}
        self._send_lock = threading.Lock()
        self._server_addr = config.get(CONF_SERVER, "")
        self._broadcast_addr = config.get(CONF_BROADCAST, "")

        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind((UDP_IP, UDP_PORT))

        if self._server_addr == "":
            # no specific server address given, use hostname
            self._server_addr = socket.gethostbyname(socket.getfqdn())

        if self._broadcast_addr == "":
            # make best guess for broadcast address
            addr = ipaddress.ip_interface(self._server_addr + "/24")
            self._broadcast_addr = str(addr.network.broadcast_address)

    def get_sequence(self):
        """ Return next LIFX packet sequence number. """

        # return next packet sequence number
        with self._seq["lock"]:
            self._seq["sequence"] = \
                (self._seq["sequence"] + 1) % SEQUENCE_COUNT
            return self._seq["sequence"] + SEQUENCE_BASE

    def probe(self, address=None):
        """ Probe given address for LIFX bulb. """
        if address is None:
            address = self._broadcast_addr

        if self._sock is not None:
            sequence = self.get_sequence()

            # create "get" message
            payload = gen_payload_get(sequence)

            with self._send_lock:
                try:
                    _LOGGER.debug("tx [%s] type [%d] sequence [%d]",
                                  address, PayloadType.GET, sequence)
                    self._sock.sendto(payload, (address, UDP_PORT))
                # pylint: disable=broad-except
                except Exception as exc:
                    _LOGGER.error("error while probing %s [%s]", address, exc)

    # pylint: disable=unused-argument
    def poll(self, now):
        """ Probe for LIFX bulbs. """
        self.probe()

    @property
    def sock(self):
        """ Return communication socket. """
        return self._sock

    @property
    def acks(self):
        """ Return list of ack packet times. """
        return self._acks

    @property
    def send_lock(self):
        """ Return communication lock. """
        return self._send_lock

    @property
    def server_addr(self):
        """ Return packet listener bind address. """
        return self._server_addr


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Set up LIFX platform. """
    data = LIFXData(config)

    listener = threading.Thread(target=packet_listener,
                                args=(data, add_devices_callback))
    listener.daemon = True
    listener.start()

    # register our poll service
    track_time_change(hass, data.poll, second=10)

    data.probe()


def convert_rgb_to_hsv(rgb):
    """ Convert HASS RGB values to LIFX HSV values. """
    red, green, blue = [_ / BYTE_MAX for _ in rgb]

    hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)

    hue *= HUE_MAX
    saturation *= SATURATION_MAX
    brightness *= BRIGHTNESS_MAX

    return [hue, saturation, brightness]


# pylint: disable=too-many-instance-attributes
class LIFXLight(Light):
    """ Provides LIFX light. """
    # pylint: disable=too-many-arguments
    def __init__(self, data, ipaddr, name, power, hue,
                 saturation, brightness, kelvin):
        self._ip = ipaddr
        self.set_name(name)
        self.set_power(power)
        self.set_color(hue, saturation, brightness, kelvin)

        self._data = data
        self._queue = queue.Queue(maxsize=5)
        self._sender = threading.Thread(target=self.command_sender)
        self._sender.daemon = True
        self._sender.start()

    def command_sender(self):
        """ Sender function for bulb. """
        while True:
            try:
                kwargs = self._queue.get()

                seq = self._data.get_sequence()

                payloadtype = kwargs["payloadtype"]

                self._data.acks[seq] = 0

                ack = False
                for i in range(RETRIES):
                    with self._data.send_lock:
                        if payloadtype == PayloadType.SETCOLOR:
                            payload = gen_payload_setcolor(seq,
                                                           kwargs["hue"],
                                                           kwargs["sat"],
                                                           kwargs["bri"],
                                                           kwargs["kel"])
                        elif payloadtype == PayloadType.SETPOWER2:
                            payload = gen_payload_setpower(seq,
                                                           kwargs["power"])
                        elif payloadtype == PayloadType.GET:
                            payload = gen_payload_get(seq)
                        else:
                            break

                        try:
                            _LOGGER.debug("tx [%s] type [%d] sequence [%d]",
                                          self._ip, payloadtype, seq)
                            self._data.sock.sendto(payload,
                                                   (self._ip, UDP_PORT))
                        # pylint: disable=broad-except
                        except Exception as exc:
                            _LOGGER.error("error sending to %s [%s]",
                                          self.name, exc)
                            break

                    # increase wait time as more packets are not ack'd
                    time.sleep(DELAY * (i * 1.5 + 1))

                    # do we have an ACK?
                    if time.time() - self._data.acks[seq] < MAX_ACK_AGE:
                        ack = True

                        if payloadtype == PayloadType.SETCOLOR:
                            self.set_color(kwargs["hue"], kwargs["sat"],
                                           kwargs["bri"], kwargs["kel"])
                            self.update_ha_state()
                        elif payloadtype == PayloadType.SETPOWER2:
                            self.set_power(kwargs["power"])
                            if not kwargs["delay_upd"]:
                                self.update_ha_state()
                        break

                if not ack:
                    _LOGGER.warn("Packet %d not ACK'd", seq)

            # pylint: disable=broad-except
            except Exception as exc:
                _LOGGER.error("Unable to process command [%s]", exc)

    @property
    def should_poll(self):
        """ No polling needed for an lifx light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def ipaddr(self):
        """ Returns the ip of the device. """
        return self._ip

    @property
    def rgb_color(self):
        """ Returns RGB value. """
        return self._rgb

    @property
    def brightness(self):
        """ Returns brightness of this light between 0..255. """
        return int(self._bri / (BYTE_MAX + 1))

    @property
    def color_temp(self):
        """ Returns color temperature. """
        return int(TEMP_MIN_HASS + (TEMP_MAX_HASS - TEMP_MIN_HASS) *
                   (self._kel - TEMP_MIN) / (TEMP_MAX - TEMP_MIN))

    @property
    def is_on(self):
        """ True if device is on. """
        return self._power != 0

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        _LOGGER.info(kwargs)

        send = False

        if ATTR_RGB_COLOR in kwargs:
            hue, saturation, brightness = \
                convert_rgb_to_hsv(kwargs[ATTR_RGB_COLOR])
            send = True
        else:
            hue = self._hue
            saturation = self._sat
            brightness = self._bri

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * (BYTE_MAX + 1)
            send = True
        else:
            brightness = self._bri

        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(((TEMP_MAX - TEMP_MIN) *
                          (kwargs[ATTR_COLOR_TEMP] - TEMP_MIN_HASS) /
                          (TEMP_MAX_HASS - TEMP_MIN_HASS)) + TEMP_MIN)
            send = True
        else:
            kelvin = self._kel

        if brightness == 0:
            self.send_setpower(Power.BULB_OFF, False)

        else:
            if self._power == 0:
                self.send_setpower(Power.BULB_ON, send)

            if send:
                self.send_setcolor(hue, saturation, brightness, kelvin)

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.send_setpower(Power.BULB_OFF, False)

    def send_setpower(self, power, delay_upd=False):
        """ Send setpower message. """
        cmd = {"payloadtype": PayloadType.SETPOWER2,
               "power": power,
               "delay_upd": delay_upd}
        self._queue.put(cmd)

    def send_setcolor(self, hue, sat, bri, kel):
        """ Send setcolor message. """
        cmd = {"payloadtype": PayloadType.SETCOLOR,
               "hue": hue,
               "sat": sat,
               "bri": bri,
               "kel": kel}
        self._queue.put(cmd)

    def set_name(self, name):
        """ Set device name. """
        self._name = name

    def set_power(self, power):
        """ Set power state value. """
        self._power = (power != 0)

    def set_color(self, hue, sat, bri, kel):
        """ Set color state values. """
        self._hue = hue
        self._sat = sat
        self._bri = bri
        self._kel = kel

        red, green, blue = colorsys.hsv_to_rgb(hue / HUE_MAX,
                                               sat / SATURATION_MAX,
                                               bri / BRIGHTNESS_MAX)

        self._rgb = [int(red * BYTE_MAX),
                     int(green * BYTE_MAX),
                     int(blue * BYTE_MAX)]
