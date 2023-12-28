"""Fever Smart API"""
import logging

from bluetooth_sensor_state_data import BluetoothData
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import DeviceClass, Units

DEVICE_SIGNATURE = "0201040303"  # Android app starts with this (so zero index)

PATCH_MESSAGE_FLAG_A = "0918"  # general broadcast (not encryted?)
PATCH_MESSAGE_FLAG_B = "0a18"  # temp broadcast (encrypted)

FEVER_SMART_MANUFACTURER_ID = 8199

MAC_TO_KEY = {
    "B4:E7:82:03:E2:B1": "0m0d3s2c",
    "B4:E7:82:4F:EE:E7": "0m0d3s2c",
}

_LOGGER = logging.getLogger(__name__)


class FeverSmartAdvParser(BluetoothData):
    """Date update for INKBIRD Bluetooth devices."""

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.info("Starting update")
        manufacturer_data = service_info.manufacturer_data

        if not manufacturer_data:
            return

        # Is it this device?
        if FEVER_SMART_MANUFACTURER_ID not in manufacturer_data:
            return

        adv_value = manufacturer_data[FEVER_SMART_MANUFACTURER_ID]

        # Convert back to raw bytes
        raw_adv = (
            FEVER_SMART_MANUFACTURER_ID.to_bytes(length=2, byteorder="little")
            + adv_value
        )
        # Only for 0918 message
        # Android app starts with: 0201040303
        hex_adv = "0201040303091817ff" + raw_adv.hex()

        # 0201040303091817ff
        # Flags
        # 02 01 04
        # Servies
        # 03 03 09 18
        # mnf data
        # 17 ff (mnf_id) + message

        # So this is fairly easy to remake!

        message = self.process(hex_adv, MAC_TO_KEY[service_info.address])

        _LOGGER.warning("Fever Smart Mac: %s Adv: %s", service_info.address, message)

        if message is None:
            return

        self.set_device_type("Fever Smart")
        self.set_device_manufacturer("Nurofen")
        self.set_device_name(f"Fever Smart {0}".format(message["device_id"]))

        self.update_sensor(
            key=DeviceClass.TEMPERATURE,
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
            native_value=message["temp"],
        )
        return

    @staticmethod
    def parse_device_id(hex_device_id: str, flag: bool):
        # if flag:

        # if not flag:
        # Base 16 to 2 then padd to 32
        temp = bin(int(hex_device_id, 16))[2:].zfill(32)

        partA = int(temp[1:6], 2)
        partB = str(int(temp[6:12], 2)).zfill(2)
        partC = int(temp[12:32], 2)

        return chr(partA + 66) + partB + "/" + f"{partC:08}"

    @staticmethod
    def make_key(key, deviceId, mac_size_bytes):
        if len(key) != 8:
            raise Exception("Key wrong length")

        if len(deviceId) != 8:  # first 4 bytes of deviceId
            raise Exception("deviceId wrong length")

        digest = hashes.Hash(hashes.SHA256())
        digest.update(bytes(key, "utf-8"))
        digest.update(bytes.fromhex(deviceId))
        return digest.finalize()[0:16]

    def decrypt(
        key: str,
        raw_device_id,
        nonce,
        associated_text,  # AEADParameters.associatedText
        encrypted_message,
        mac_size_bytes: int = 4,
    ):
        hashedKey = FeverSmartAdvParser.make_key(key, raw_device_id, mac_size_bytes)
        hashedNonce = bytes.fromhex(nonce)
        hashed_associated_text = bytes.fromhex(associated_text)
        tmp = bytes.fromhex(encrypted_message)
        encrypted_message_bytes = tmp[:-4]
        mac_bytes = tmp[-4:]  # Last 4 bytes are mac

        aesccm = AESCCM(key=hashedKey, tag_length=mac_size_bytes)

        try:
            plaintext = aesccm.decrypt(hashedNonce, tmp, hashed_associated_text)
        except InvalidTag:
            # Log?
            # I'm not sure when this occurs yet
            return None

        return plaintext.hex()

    @staticmethod
    def process(raw_offset, key):
        if not raw_offset.startswith(DEVICE_SIGNATURE):
            print("Not matching signature")
            return

        nonce_a = raw_offset[6:16]  # overlaps with patch message
        patch_message_flag = raw_offset[10:14]
        raw_device_id = raw_offset[18:26]
        nonce_b = raw_offset[26:42]
        encrypted_message = raw_offset[42:62]

        # Unknown
        some_time = int(raw_offset[26:28], 16)
        # int parseInt = (((Integer.parseInt(str3.substring(14, 16), 16) - 1) - 4) - 1) * 2;
        # number of messages?

        device_id = FeverSmartAdvParser.parse_device_id(raw_device_id, False)
        nonce_int = int(
            nonce_b, 16
        )  # BigInteger bigInteger = new BigInteger(this.scanRecord.substring(26, 42), 16);

        message = FeverSmartAdvParser.decrypt(
            key,
            raw_device_id,
            nonce_a
            + nonce_b,  # scanRecord.substring(6, 16) + scanRecord.substring(26, 42), nonce
            raw_offset[
                10:26
            ],  # scanRecord.substring(10, 26), AEADParameters.associatedText
            encrypted_message,  # scanRecord.substring(42, 62), THIS IS THE ENCRYPTED MESSAGE
            4,  # constant (MacSize == 32 )
        )

        if message is None:
            return

        battery = int(message[4:6], 16)
        raw_temp = int(message[0:4], 16)  # TODO: Deal with int overflow on this...
        firmware_version = str(int(message[6:7], 16)) + "." + str(int(message[7:8], 16))
        counter = int(message[8:12], 16)  # rolling count

        temp = 0.0

        if patch_message_flag == PATCH_MESSAGE_FLAG_A:
            temp = raw_temp * 0.0625
            # Other app also adds 0.28f
            #

        if patch_message_flag == PATCH_MESSAGE_FLAG_B:  # Temp here is offset!
            raw_temp_float = float(raw_temp)
            temp = 0.0
            if raw_temp > 2.0**15.0:
                temp = 0.0 - (raw_temp_float - 2.0**15.0) * 1.0e-4
            else:
                temp = 1.0e-4 * raw_temp_float

        return {
            "some_time": some_time,
            "device_id": device_id,
            "firmware_version": firmware_version,
            "patch_message_flag": patch_message_flag,
            "counter": counter,
            "raw_message": raw_offset,
            "battery": battery,
            "raw_temp": raw_temp,
            "temp": temp,
        }
