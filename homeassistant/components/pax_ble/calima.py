#!/usr/bin/env python3.6

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from homeassistant.components import bluetooth
from struct import pack, unpack
import time
import datetime
import subprocess
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio
import binascii
import math
from collections import namedtuple
import logging

_LOGGER = logging.getLogger(__name__)

Fanspeeds = namedtuple('Fanspeeds', 'Humidity Light Trickle')
Fanspeeds.__new__.__defaults__ = (2250, 1625, 1000)
Time = namedtuple('Time', 'DayOfWeek Hour Minute Second')
Sensitivity = namedtuple('Sensitivity', 'HumidityOn Humidity LightOn Light')
LightSensorSettings = namedtuple('LightSensorSettings', 'DelayedStart RunningTime')
HeatDistributorSettings = namedtuple('HeatDistributorSettings', 'TemperatureLimit FanSpeedBelow FanSpeedAbove')
SilentHours = namedtuple('SilentHours', 'On StartingHour StartingMinute EndingHour EndingMinute')
TrickleDays = namedtuple('TrickleDays', 'Weekdays Weekends')
BoostMode = namedtuple('BoostMode', 'OnOff Speed Seconds')

FanState = namedtuple('FanState', 'Humidity Temp Light RPM Mode')

# Stolen defines for each characteristic (taken from a decompiled Android App)
CHARACTERISTIC_APPEARANCE = "00002a01-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_AUTOMATIC_CYCLES = "f508408a-508b-41c6-aa57-61d1fd0d5c39"
CHARACTERISTIC_BASIC_VENTILATION = "faa49e09-a79c-4725-b197-bdc57c67dc32"
CHARACTERISTIC_BOOST = "118c949c-28c8-4139-b0b3-36657fd055a9"
CHARACTERISTIC_CLOCK = "6dec478e-ae0b-4186-9d82-13dda03c0682"
CHARACTERISTIC_DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_FACTORY_SETTINGS_CHANGED = "63b04af9-24c0-4e5d-a69c-94eb9c5707b4"
CHARACTERISTIC_FAN_DESCRIPTION = "b85fa07a-9382-4838-871c-81d045dcc2ff"
CHARACTERISTIC_FIRMWARE_REVISION = "00002a26-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_HARDWARE_REVISION = "00002a27-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_SOFTWARE_REVISION = "00002a28-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_LED = "8b850c04-dc18-44d2-9501-7662d65ba36e"
CHARACTERISTIC_LEVEL_OF_FAN_SPEED = "1488a757-35bc-4ec8-9a6b-9ecf1502778e"
CHARACTERISTIC_MANUFACTURER_NAME = "00002a29-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_MODE = "90cabcd1-bcda-4167-85d8-16dcd8ab6a6b"
CHARACTERISTIC_MODEL_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_NIGHT_MODE = "b5836b55-57bd-433e-8480-46e4993c5ac0"
CHARACTERISTIC_PIN_CODE = "4cad343a-209a-40b7-b911-4d9b3df569b2"
CHARACTERISTIC_PIN_CONFIRMATION = "d1ae6b70-ee12-4f6d-b166-d2063dcaffe1"
CHARACTERISTIC_RESET = "ff5f7c4f-2606-4c69-b360-15aaea58ad5f"
CHARACTERISTIC_SENSITIVITY = "e782e131-6ce1-4191-a8db-f4304d7610f1"
CHARACTERISTIC_SENSOR_DATA = "528b80e8-c47a-4c0a-bdf1-916a7748f412"
CHARACTERISTIC_SERIAL_NUMBER = "00002a25-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_SOFTWARE_REVISION = "00002a28-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_STATUS = "25a824ad-3021-4de9-9f2f-60cf8d17bded"
CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR = "a22eae12-dba8-49f3-9c69-1721dcff1d96"
CHARACTERISTIC_TIME_FUNCTIONS = "49c616de-02b1-4b67-b237-90f66793a6f2"

class Calima:
    def __init__(self, hass, mac, pin):
        self._hass = hass
        self._dev = None
        self._mac = mac
        self._pin = pin

    async def __del__(self):
        await self.disconnect()

    def isConnected(self):
        if self._dev is None:
            return False
        else:
            return self._dev.is_connected

    async def authorize(self):
        await self.setAuth(self._pin)
        
    async def connect(self, retries=1):  
        await self.disconnect()
        tries = 0
        while (tries < retries):
            tries += 1
            try:
                d = bluetooth.async_ble_device_from_address(self._hass, self._mac.upper())
                if not d:
                    raise BleakError(f"A device with address {self._mac} could not be found.")
                
                self._dev = BleakClient(d)
                
                ret = await self._dev.connect()
                if ret:
                    _LOGGER.debug("Connected to {}".format(self._mac))
                    break
            except Exception as e:
                if tries == retries:
                    _LOGGER.info("Not able to connect to {}".format(self._mac))
                else:
                    _LOGGER.debug("Retrying {}".format(self._mac))

    async def disconnect(self):
        if self._dev is not None:
            await self._dev.disconnect()
            self._dev = None

    def _bToStr(self, val):
        return binascii.b2a_hex(val).decode('utf-8')

    async def _readUUID(self, uuid):
        val = await self._dev.read_gatt_char(uuid)
        return val

    async def _readHandle(self, handle):
        val = await self._dev.read_gatt_char(char_specifier=handle)
        return val

    async def _writeUUID(self, uuid, val):
        await self._dev.write_gatt_char(char_specifier=uuid, data=val, response=True)

    # --- Generic GATT Characteristics

    async def getDeviceName(self):
        # Why does UUID "0x2" fail here? Doesn't when testing from my PC...
        return (await self._readHandle(CHARACTERISTIC_MODEL_NAME)).decode('ascii')

    async def getModelNumber(self):
        return (await self._readHandle(0xd)).decode('ascii')

    async def getSerialNumber(self):
        return (await self._readHandle(0xb)).decode('ascii')

    async def getHardwareRevision(self):
        return (await self._readHandle(0xf)).decode('ascii')

    async def getFirmwareRevision(self):
        return (await self._readHandle(0x11)).decode('ascii')

    async def getSoftwareRevision(self):
        return (await self._readHandle(0x13)).decode('ascii')

    async def getManufacturer(self):
        return (await self._readHandle(0x15)).decode('ascii')

    # --- Onwards to PAX characteristics

    async def setAuth(self, pin):
        await self._writeUUID(CHARACTERISTIC_PIN_CODE, pack("<I", int(pin))) 

    async def checkAuth(self):
        return bool(unpack('<I', await self._readUUID(CHARACTERISTIC_PIN_CONFIRMATION)))

    async def setAlias(self, name):
        await self._writeUUID(CHARACTERISTIC_FAN_DESCRIPTION, pack('20s', bytearray(name, 'utf-8')))

    async def getAlias(self):
        return await self._readUUID(CHARACTERISTIC_FAN_DESCRIPTION).decode('utf-8')

    async def getIsClockSet(self):
        return self._bToStr(await self._readUUID(CHARACTERISTIC_STATUS))

    async def getState(self):
        # Short Short Short Short    Byte Short Byte
        # Hum   Temp  Light FanSpeed Mode Tbd   Tbd
        v = unpack('<4HBHB', await self._readUUID(CHARACTERISTIC_SENSOR_DATA))
        _LOGGER.debug("Read Fan States: %s", v)
        
        trigger = "No trigger"
        if ((v[4] >> 4) & 1) == 1:
            trigger = "Boost"
        elif ((v[4] >> 6) & 3) == 3:
            trigger = "Switch"
        elif (v[4] & 3) == 1:
            trigger = "Trickle ventilation"
        elif (v[4] & 3) == 2:
            trigger = "Light ventilation"
        elif (v[4] & 3) == 3: # Note that the trigger might be active, but mode must be enabled to be activated
            trigger = "Humidity ventilation"

        return FanState(round(math.log2(v[0]-30)*10, 2) if v[0] > 30 else 0, v[1]/4 - 2.6, v[2], v[3], trigger)

    async def getFactorySettingsChanged(self):
        return unpack('<?', await self._readUUID(CHARACTERISTIC_FACTORY_SETTINGS_CHANGED))

    async def getMode(self):
        v = unpack('<B', await self._readUUID(CHARACTERISTIC_MODE))
        if v[0] == 0:
            return "MultiMode"
        elif v[0] == 1:
            return "DraftShutterMode"
        elif v[0] == 2:
            return "WallSwitchExtendedRuntimeMode"
        elif v[0] == 3:
            return "WallSwitchNoExtendedRuntimeMode"
        elif v[0] == 4:
            return "HeatDistributionMode"

    async def setFanSpeedSettings(self, humidity=2250, light=1625, trickle=1000):
        for val in (humidity, light, trickle):
            if (val % 25 != 0):
                raise ValueError("Speeds should be multiples of 25")
            if (val > 2500 or val < 0):
                raise ValueError("Speeds must be between 0 and 2500 rpm")

        _LOGGER.debug("Calima setFanSpeedSettings: %s %s %s", humidity, light, trickle)

        await self._writeUUID(CHARACTERISTIC_LEVEL_OF_FAN_SPEED, pack('<HHH', humidity, light, trickle))

    async def getFanSpeedSettings(self):
        return Fanspeeds._make(unpack('<HHH', await self._readUUID(CHARACTERISTIC_LEVEL_OF_FAN_SPEED)))

    async def setSensorsSensitivity(self, humidity, light):
        if humidity > 3 or humidity < 0:
            raise ValueError("Humidity sensitivity must be between 0-3")
        if light > 3 or light < 0:
            raise ValueError("Light sensitivity must be between 0-3")

        value = pack('<4B', bool(humidity), humidity, bool(light), light)
        await self._writeUUID(CHARACTERISTIC_SENSITIVITY, value)

    async def getSensorsSensitivity(self):
        # Hum Active | Hum Sensitivity | Light Active | Light Sensitivity
        # We fix so that Sensitivity = 0 if active = 0
        l = Sensitivity._make(unpack('<4B', await self._readUUID(CHARACTERISTIC_SENSITIVITY)))

        return Sensitivity._make(unpack('<4B', bytearray([l.HumidityOn, l.HumidityOn and l.Humidity, l.LightOn, l.LightOn and l.Light])))

    async def setLightSensorSettings(self, delayed, running):
        if delayed not in (0, 5, 10):
            raise ValueError("Delayed must be 0, 5 or 10 minutes")
        if running not in (5, 10, 15, 30, 60):
            raise ValueError("Running time must be 5, 10, 15, 30 or 60 minutes")

        await self._writeUUID(CHARACTERISTIC_TIME_FUNCTIONS, pack('<2B', delayed, running))

    async def getLightSensorSettings(self):
        return LightSensorSettings._make(unpack('<2B', await self._readUUID(CHARACTERISTIC_TIME_FUNCTIONS)))

    async def getHeatDistributor(self):
        return HeatDistributorSettings._make(unpack('<BHH', await self._readUUID(CHARACTERISTIC_TEMP_HEAT_DISTRIBUTOR)))

    async def setBoostMode(self, on, speed, seconds):
        if speed % 25:
            raise ValueError("Speed must be a multiple of 25")
        if not on:
            speed = 0
            seconds = 0

        await self._writeUUID(CHARACTERISTIC_BOOST, pack('<BHH', on, speed, seconds))

    async def getBoostMode(self):
        return BoostMode._make(unpack('<BHH', await self._readUUID(CHARACTERISTIC_BOOST)))

    async def getLed(self):
        return self._bToStr(awaitself._readUUID(CHARACTERISTIC_LED))

    async def setAutomaticCycles(self, setting):
        if setting < 0 or setting > 3:
            raise ValueError("Setting must be between 0-3")

        await self._writeUUID(CHARACTERISTIC_AUTOMATIC_CYCLES, pack('<B', setting))

    async def getAutomaticCycles(self):
        return unpack('<B', await self._readUUID(CHARACTERISTIC_AUTOMATIC_CYCLES))[0]

    async def setTime(self, dayofweek, hour, minute, second):
        await self._writeUUID(CHARACTERISTIC_CLOCK, pack('<4B', dayofweek, hour, minute, second))

    async def getTime(self):
        return Time._make(unpack('<BBBB', await self._readUUID(CHARACTERISTIC_CLOCK)))

    async def setTimeToNow(self):
        now = datetime.datetime.now()
        await self.setTime(now.isoweekday(), now.hour, now.minute, now.second)

    async def setSilentHours(self, on, startingHours, startingMinutes, endingHours, endingMinutes):
        if startingHours < 0 or startingHours > 23:
            raise ValueError("Starting hour is an invalid number")
        if endingHours < 0 or endingHours > 23:
            raise ValueError("Ending hour is an invalid number")
        if startingMinutes < 0 or startingMinutes > 59:
            raise ValueError("Starting minute is an invalid number")
        if endingMinutes < 0 or endingMinutes > 59:
            raise ValueError("Ending minute is an invalid number")

        value = pack('<5B', int(on),
                     startingHours, startingMinutes,
                     endingHours, endingMinutes)
        await self._writeUUID(CHARACTERISTIC_NIGHT_MODE, value)

    async def getSilentHours(self):
        return SilentHours._make(unpack('<5B', await self._readUUID(CHARACTERISTIC_NIGHT_MODE)))

    async def setTrickleDays(self, weekdays, weekends):
        await self._writeUUID(CHARACTERISTIC_BASIC_VENTILATION, pack('<2B', weekdays, weekends))

    async def getTrickleDays(self):
        return TrickleDays._make(unpack('<2B', await self._readUUID(CHARACTERISTIC_BASIC_VENTILATION)))

    async def getReset(self): # Should be write
        return await self._readUUID(CHARACTERISTIC_RESET)

    async def resetDevice(self): # Dangerous
        await self._writeUUID(CHARACTERISTIC_RESET, pack('<I', 120))

    async def resetValues(self): # Danguerous
        await self._writeUUID(CHARACTERISTIC_RESET, pack('<I', 85))
