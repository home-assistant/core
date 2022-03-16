"""SamsungTV Encrypted."""
import hashlib
import logging
import re
import struct
from typing import Dict, Optional

import aiohttp
from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    CipherContext,
    algorithms,
    modes,
)

LOGGER = logging.getLogger(__name__)
BLOCK_SIZE = 16
SHA_DIGEST_LENGTH = 20
PUBLIC_KEY = "2cb12bb2cbf7cec713c0fff7b59ae68a96784ae517f41d259a45d20556177c0ffe951ca60ec03a990c9412619d1bee30adc7773088c5721664cffcedacf6d251cb4b76e2fd7aef09b3ae9f9496ac8d94ed2b262eee37291c8b237e880cc7c021fb1be0881f3d0bffa4234d3b8e6a61530c00473ce169c025f47fcc001d9b8051"
PRIVATE_KEY = "2fd6334713816fae018cdee4656c5033a8d6b00e8eaea07b3624999242e96247112dcd019c4191f4643c3ce1605002b2e506e7f1d1ef8d9b8044e46d37c0d5263216a87cd783aa185490436c4a0cb2c524e15bc1bfeae703bcbc4b74a0540202e8d79cadaae85c6f9c218bc1107d1f5b4b9bd87160e782f4e436eeb17485ab4d"
WB_KEY = "abbb120c09e7114243d1fa0102163b27"
TRANS_KEY = "6c9474469ddf7578f3e5ad8a4c703d99"
PRIME = "b361eb0ab01c3439f2c16ffda7b05e3e320701ebee3e249123c3586765fd5bf6c1dfa88bb6bb5da3fde74737cd88b6a26c5ca31d81d18e3515533d08df619317063224cf0943a2f29a5fe60c1c31ddf28334ed76a6478a1122fb24c4a94c8711617ddfe90cf02e643cd82d4748d6d4a7ca2f47d88563aa2baf6482e124acd7dd"


def _encrypt_parameter_data_with_aes(data: bytes) -> bytes:
    iv = b"\x00" * BLOCK_SIZE
    output = b""
    for num in range(0, 128, 16):
        cipher = Cipher(algorithms.AES(bytes.fromhex(WB_KEY)), modes.CBC(iv))
        encryptor: CipherContext = cipher.encryptor()
        output += encryptor.update(data[num : num + 16]) + encryptor.finalize()

    return output


def _decrypt_parameter_data_with_aes(data: bytes) -> bytes:
    iv = b"\x00" * BLOCK_SIZE
    output = b""
    for num in range(0, 128, 16):
        cipher = Cipher(algorithms.AES(bytes.fromhex(WB_KEY)), modes.CBC(iv))
        decryptor: CipherContext = cipher.decryptor()
        output += decryptor.update(data[num : num + 16]) + decryptor.finalize()

    return output


def _apply_samy_go_key_transform(data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(bytes.fromhex(TRANS_KEY)), modes.ECB())
    encryptor: CipherContext = cipher.encryptor()

    return encryptor.update(data) + encryptor.finalize()  # type:ignore[no-any-return]


def _generate_server_hello(user_id: str, pin: str) -> Dict[str, bytes]:
    sha1 = hashlib.sha1()
    sha1.update(pin.encode("utf-8"))
    pin_hash = sha1.digest()
    aes_key = pin_hash[:16]
    LOGGER.debug("AES key: %s", aes_key.hex())

    iv = b"\x00" * BLOCK_SIZE
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor: CipherContext = cipher.encryptor()
    encrypted = encryptor.update(bytes.fromhex(PUBLIC_KEY)) + encryptor.finalize()
    LOGGER.debug("AES encrypted: %s", encrypted.hex())

    swapped = _encrypt_parameter_data_with_aes(encrypted)
    LOGGER.debug("AES swapped: %s", swapped.hex())

    data = struct.pack(">I", len(user_id)) + user_id.encode("utf-8") + swapped
    LOGGER.debug("data buffer: %s", data.hex().upper())

    sha1 = hashlib.sha1()
    sha1.update(data)
    data_hash = sha1.digest()
    LOGGER.debug("hash: %s", data_hash.hex())
    server_hello = (
        b"\x01\x02"
        + b"\x00" * 5
        + struct.pack(">I", len(user_id) + 132)
        + data
        + b"\x00" * 5
    )

    return {"serverHello": server_hello, "hash": data_hash, "AES_key": aes_key}


def _parse_client_hello(
    client_hello: str, data_hash: bytes, aes_key: bytes, user_id: str
) -> Optional[Dict[str, bytes]]:
    USER_ID_POS = 15
    USER_ID_LEN_POS = 11
    GX_SIZE = 0x80

    LOGGER.debug("hello: %s", client_hello)
    data = bytes.fromhex(client_hello)
    # firstLen = struct.unpack(">I", data[7:11])[0]
    userIdLen = struct.unpack(">I", data[11:15])[0]
    # destLen = userIdLen + 132 + SHA_DIGEST_LENGTH  # Always equals firstLen????
    thirdLen = userIdLen + 132
    LOGGER.debug("thirdLen: %s", str(thirdLen))

    dest = data[USER_ID_LEN_POS : thirdLen + USER_ID_LEN_POS] + data_hash
    LOGGER.debug("dest: %s", dest.hex())

    userId = data[USER_ID_POS : userIdLen + USER_ID_POS]
    LOGGER.debug("userId: %s", userId.decode("utf-8"))

    pEncWBGx = data[USER_ID_POS + userIdLen : GX_SIZE + USER_ID_POS + userIdLen]
    LOGGER.debug("pEncWBGx: %s", pEncWBGx.hex())

    pEncGx = _decrypt_parameter_data_with_aes(pEncWBGx)
    LOGGER.debug("pEncGx: %s", pEncGx.hex())

    iv = b"\x00" * BLOCK_SIZE
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor: CipherContext = cipher.decryptor()
    pGx = decryptor.update(pEncGx) + decryptor.finalize()
    LOGGER.debug("pGx: %s", pGx.hex())

    bnPGx = int(pGx.hex(), 16)
    bnPrime = int(PRIME, 16)
    bnPrivateKey = int(PRIVATE_KEY, 16)
    secret = bytes.fromhex(
        hex(pow(bnPGx, bnPrivateKey, bnPrime)).rstrip("L").lstrip("0x")
    )
    LOGGER.debug("secret: %s", secret.hex())

    dataHash2 = data[
        USER_ID_POS
        + userIdLen
        + GX_SIZE : USER_ID_POS
        + userIdLen
        + GX_SIZE
        + SHA_DIGEST_LENGTH
    ]
    LOGGER.debug("hash2: %s", dataHash2.hex())

    secret2 = userId + secret
    LOGGER.debug("secret2: %s", secret2.hex())

    sha1 = hashlib.sha1()
    sha1.update(secret2)
    dataHash3 = sha1.digest()
    LOGGER.debug("hash3: %s", dataHash3.hex())
    if dataHash2 != dataHash3:
        LOGGER.error("Pin error!!!")
        return None

    LOGGER.info("Pin OK")
    flagPos = userIdLen + USER_ID_POS + GX_SIZE + SHA_DIGEST_LENGTH
    if ord(data[flagPos : flagPos + 1]):
        LOGGER.error("First flag error!!!")
        return None

    flagPos = userIdLen + USER_ID_POS + GX_SIZE + SHA_DIGEST_LENGTH
    if struct.unpack(">I", data[flagPos + 1 : flagPos + 5])[0]:
        LOGGER.error("Second flag error!!!")
        return None

    sha1 = hashlib.sha1()
    sha1.update(dest)
    dest_hash = sha1.digest()
    LOGGER.debug("dest_hash: %s", dest_hash.hex())

    finalBuffer = (
        userId + user_id.encode("utf-8") + pGx + bytes.fromhex(PUBLIC_KEY) + secret
    )
    sha1 = hashlib.sha1()
    sha1.update(finalBuffer)
    SKPrime = sha1.digest()
    LOGGER.debug("SKPrime: %s", SKPrime.hex())
    sha1 = hashlib.sha1()
    sha1.update(SKPrime + b"\x00")
    SKPrimeHash = sha1.digest()
    LOGGER.debug("SKPrimeHash: %s", SKPrimeHash.hex())
    ctx = _apply_samy_go_key_transform(SKPrimeHash[:16])

    return {"ctx": ctx, "SKPrime": SKPrime}


def _generate_server_acknowledge(skprime: bytes) -> str:
    sha1 = hashlib.sha1()
    sha1.update(skprime + b"\x01")
    skprime_hash = sha1.digest()

    return "0103000000000000000014" + skprime_hash.hex().upper() + "0000000000"


def _parse_client_acknowledge(client_ack: str, skprime: bytes) -> bool:
    sha1 = hashlib.sha1()
    sha1.update(skprime + b"\x02")
    skprime_hash = sha1.digest()
    calculate_ack = "0104000000000000000014" + skprime_hash.hex().upper() + "0000000000"

    return client_ack == calculate_ack


class SamsungTVEncryptedWSAsyncAuthenticator:
    USER_ID = "654321"
    APP_ID = "12345"
    DEVICE_ID = "7e509404-9d7c-46b4-8f6a-e2a9668ad184"

    def __init__(
        self,
        host: str,
        *,
        web_session: aiohttp.ClientSession,
        port: int = 8080,
        timeout: Optional[float] = None,
    ) -> None:
        self._host = host
        self._web_session = web_session
        self._port = port
        self._timeout = timeout
        self._sk_prime: Optional[bytes] = None

    def _get_full_url(self, route: str) -> str:
        return f"http://{self._host}:{self._port}/{route}"

    def _get_full_request_url(self, step: int) -> str:
        return self._get_full_url(
            f"ws/pairing?step={step}&app_id={self.APP_ID}&device_id={self.DEVICE_ID}"
        )

    async def _show_pin_page_on_tv(self) -> None:
        url = self._get_full_url("ws/apps/CloudPINPage")
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data="pin4") as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def _check_pin_page_on_tv(self) -> bool:
        url = self._get_full_url("ws/apps/CloudPINPage")
        LOGGER.debug("Tx: GET %s", url)
        async with self._web_session.get(url) as response:
            LOGGER.debug("Rx: %s", await response.text())
            page = await response.text()
        output = re.search("state>([^<>]*)</state>", page, flags=re.IGNORECASE)
        if output is not None:
            state = output.group(1)
            LOGGER.info("Current PIN state: %s", state)
            if state == "stopped":
                return False
        return True

    async def start_pairing(self) -> None:
        if await self._check_pin_page_on_tv():
            LOGGER.info("Pin ON TV")
        else:
            LOGGER.info("Pin NOT on TV")
            await self._show_pin_page_on_tv()

    async def _first_step_of_pairing(self) -> None:
        url = self._get_full_request_url(0) + "&type=1"
        LOGGER.debug("Tx: GET %s", url)
        async with self._web_session.get(url) as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def _second_step_of_pairing(self, pin: str) -> Optional[Dict[str, bytes]]:
        hello_output = _generate_server_hello(self.USER_ID, pin)
        if not hello_output:
            return None

        content = (
            '{"auth_Data":{"auth_type":"SPC","GeneratorServerHello":"'
            + hello_output["serverHello"].hex().upper()
            + '"}}'
        )
        url = self._get_full_request_url(1)
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data=content) as response:
            LOGGER.debug("Rx: %s", await response.text())
            response_text = await response.text()

        output = re.search(
            r"request_id.*?(\d).*?GeneratorClientHello.*?:.*?(\d[0-9a-zA-Z]*)",
            response_text,
            flags=re.IGNORECASE,
        )
        if output is None:
            return None

        # request_id = output.group(1)
        client_hello = output.group(2)
        # lastRequestId = int(requestId)
        return _parse_client_hello(
            client_hello, hello_output["hash"], hello_output["AES_key"], self.USER_ID
        )

    async def try_pin(self, pin: str) -> Optional[str]:
        LOGGER.debug("Trying pin: '%s'", pin)
        await self._first_step_of_pairing()
        result = await self._second_step_of_pairing(pin)
        if result:
            LOGGER.info("Pin accepted")
            token = result["ctx"].hex()
            self._sk_prime = result["SKPrime"]
            LOGGER.info("Token (ctx): %s", token)
            return token

        LOGGER.info("Pin incorrect. Please try again")
        return None

    async def _acknowledge_exchange(self) -> str:
        assert self._sk_prime
        server_ack_message = _generate_server_acknowledge(self._sk_prime)
        content = (
            '{"auth_Data":{"auth_type":"SPC","request_id":"0","ServerAckMsg":"'
            + server_ack_message
            + '"}}'
        )
        url = self._get_full_request_url(2)
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data=content) as response:
            LOGGER.debug("Rx: %s", await response.text())
            response_text = await response.text()

        if "secure-mode" in response_text:
            raise Exception("TODO: Implement handling of encryption flag!!!!")

        output = re.search(
            r"ClientAckMsg.*?:.*?(\d[0-9a-zA-Z]*).*?session_id.*?(\d)",
            response_text,
            flags=re.IGNORECASE,
        )
        if output is None:
            raise Exception("Unable to get session_id and/or ClientAckMsg!!!")

        client_ack = output.group(1)
        assert self._sk_prime
        if not _parse_client_acknowledge(client_ack, self._sk_prime):
            raise Exception("Parse client ack message failed.")

        session_id = output.group(2)
        LOGGER.info("Got sessionId: %s", session_id)

        return session_id  # type:ignore[no-any-return]

    async def _close_pin_page_on_tv(self) -> None:
        url = self._get_full_url("ws/apps/CloudPINPage/run")
        LOGGER.debug("Tx: DELETE %s", url)
        async with self._web_session.delete(url) as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def get_session_id_and_close(self) -> str:
        session_id = await self._acknowledge_exchange()
        LOGGER.info("SessionID: %s", session_id)

        await self._close_pin_page_on_tv()
        LOGGER.info("Authorization successful")

        return session_id
