from base64 import b64encode
import binascii
import requests
import logging
import json

from homeassistant.const import ATTR_ENTITY_ID
from . import Helper

_LOGGER = logging.getLogger(__name__)

BROADLINK_CONTROLLER = 'Broadlink'
XIAOMI_CONTROLLER = 'Xiaomi'
MQTT_CONTROLLER = 'MQTT'
LOOKIN_CONTROLLER = 'LOOKin'
ESPHOME_CONTROLLER = 'ESPHome'

ENC_BASE64 = 'Base64'
ENC_HEX = 'Hex'
ENC_PRONTO = 'Pronto'
ENC_RAW = 'Raw'

BROADLINK_COMMANDS_ENCODING = [ENC_BASE64, ENC_HEX, ENC_PRONTO]
XIAOMI_COMMANDS_ENCODING = [ENC_PRONTO, ENC_RAW]
MQTT_COMMANDS_ENCODING = [ENC_RAW]
LOOKIN_COMMANDS_ENCODING = [ENC_PRONTO, ENC_RAW]
ESPHOME_COMMANDS_ENCODING = [ENC_RAW]

class Controller():
    def __init__(self, hass, controller, encoding, controller_data):
        if controller not in [
            BROADLINK_CONTROLLER, XIAOMI_CONTROLLER, 
            MQTT_CONTROLLER, LOOKIN_CONTROLLER, ESPHOME_CONTROLLER]:
            raise Exception("The controller is not supported.")

        if controller == BROADLINK_CONTROLLER:
            if encoding not in BROADLINK_COMMANDS_ENCODING:
                raise Exception("The encoding is not supported "
                                "by the Broadlink controller.")

        if controller == XIAOMI_CONTROLLER:
            if encoding not in XIAOMI_COMMANDS_ENCODING:
                raise Exception("The encoding is not supported "
                                "by the Xiaomi controller.")

        if controller == MQTT_CONTROLLER:
            if encoding not in MQTT_COMMANDS_ENCODING:
                raise Exception("The encoding is not supported "
                                "by the mqtt controller.")

        if controller == LOOKIN_CONTROLLER:
            if encoding not in LOOKIN_COMMANDS_ENCODING:
                raise Exception("The encoding is not supported "
                                "by the LOOKin controller.")

        if controller == ESPHOME_CONTROLLER:
            if encoding not in ESPHOME_COMMANDS_ENCODING:
                raise Exception("The encoding is not supported "
                                "by the ESPHome controller.")

        self.hass = hass
        self._controller = controller
        self._encoding = encoding
        self._controller_data = controller_data

    async def send(self, command):
        if self._controller == BROADLINK_CONTROLLER:
            if self._encoding == ENC_HEX:
                try:
                    command = binascii.unhexlify(command)
                    command = b64encode(command).decode('utf-8')
                except:
                    raise Exception("Error while converting "
                                    "Hex to Base64 encoding")

            if self._encoding == ENC_PRONTO:
                try:
                    command = command.replace(' ', '')
                    command = bytearray.fromhex(command)
                    command = Helper.pronto2lirc(command)
                    command = Helper.lirc2broadlink(command)
                    command = b64encode(command).decode('utf-8')
                except:
                    raise Exception("Error while converting "
                                    "Pronto to Base64 encoding")

            service_data = {
                'host': self._controller_data,
                'packet': command
            }

            await self.hass.services.async_call(
                'broadlink', 'send', service_data)


        if self._controller == XIAOMI_CONTROLLER:
            service_data = {
                ATTR_ENTITY_ID: self._controller_data,
                'command':  self._encoding.lower() + ':' + command
            }

            await self.hass.services.async_call(
               'remote', 'send_command', service_data)


        if self._controller == MQTT_CONTROLLER:
            service_data = {
                'topic': self._controller_data,
                'payload': command
            }

            await self.hass.services.async_call(
               'mqtt', 'publish', service_data)

        if self._controller == LOOKIN_CONTROLLER:
            encoding = self._encoding.lower().replace('pronto', 'prontohex')
            url = f"http://{self._controller_data}/commands/ir/" \
                  f"{encoding}/{command}"
            await self.hass.async_add_executor_job(
                requests.get, url
            )

        if self._controller == ESPHOME_CONTROLLER:
            service_data = {
                'command':  json.loads(command)
            }

            await self.hass.services.async_call(
               'esphome', self._controller_data, service_data)
