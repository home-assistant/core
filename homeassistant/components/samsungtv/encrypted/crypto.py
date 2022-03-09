"""SamsungTV Encrypted."""
# flake8: noqa
# mypy: ignore-errors
# pylint: disable=[invalid-name,missing-function-docstring,redefined-builtin,unused-variable]
import hashlib
import struct

from Crypto.Cipher import AES
from py3rijndael.rijndael import Rijndael

from . import keys

BLOCK_SIZE = 16
SHA_DIGEST_LENGTH = 20


def EncryptParameterDataWithAES(input):
    iv = b"\x00" * BLOCK_SIZE
    output = b""
    for num in range(0, 128, 16):
        cipher = AES.new(bytes.fromhex(keys.wbKey), AES.MODE_CBC, iv)
        output += cipher.encrypt(input[num : num + 16])
    return output


def DecryptParameterDataWithAES(input):
    iv = b"\x00" * BLOCK_SIZE
    output = b""
    for num in range(0, 128, 16):
        cipher = AES.new(bytes.fromhex(keys.wbKey), AES.MODE_CBC, iv)
        output += cipher.decrypt(input[num : num + 16])
    return output


def applySamyGOKeyTransform(input):
    r = Rijndael(bytes.fromhex(keys.transKey))
    return r.encrypt(input)


def generateServerHello(userId, pin):
    sha1 = hashlib.sha1()
    sha1.update(pin.encode("utf-8"))
    pinHash = sha1.digest()
    aes_key = pinHash[:16]
    print("AES key: " + aes_key.hex())
    iv = b"\x00" * BLOCK_SIZE
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(bytes.fromhex(keys.publicKey))
    print("AES encrypted: " + encrypted.hex())
    swapped = EncryptParameterDataWithAES(encrypted)
    print("AES swapped: " + swapped.hex())
    data = struct.pack(">I", len(userId)) + userId.encode("utf-8") + swapped
    print("data buffer: " + data.hex().upper())
    sha1 = hashlib.sha1()
    sha1.update(data)
    dataHash = sha1.digest()
    print("hash: " + dataHash.hex())
    serverHello = (
        b"\x01\x02"
        + b"\x00" * 5
        + struct.pack(">I", len(userId) + 132)
        + data
        + b"\x00" * 5
    )
    return {"serverHello": serverHello, "hash": dataHash, "AES_key": aes_key}


def parseClientHello(clientHello, dataHash, aesKey, gUserId):
    USER_ID_POS = 15
    USER_ID_LEN_POS = 11
    GX_SIZE = 0x80
    data = bytes.fromhex(clientHello)
    firstLen = struct.unpack(">I", data[7:11])[0]
    userIdLen = struct.unpack(">I", data[11:15])[0]
    destLen = userIdLen + 132 + SHA_DIGEST_LENGTH  # Always equals firstLen????:)
    thirdLen = userIdLen + 132
    print("thirdLen: " + str(thirdLen))
    print("hello: " + data.hex())
    dest = data[USER_ID_LEN_POS : thirdLen + USER_ID_LEN_POS] + dataHash
    print("dest: " + dest.hex())
    userId = data[USER_ID_POS : userIdLen + USER_ID_POS]
    print("userId: " + userId.decode("utf-8"))
    pEncWBGx = data[USER_ID_POS + userIdLen : GX_SIZE + USER_ID_POS + userIdLen]
    print("pEncWBGx: " + pEncWBGx.hex())
    pEncGx = DecryptParameterDataWithAES(pEncWBGx)
    print("pEncGx: " + pEncGx.hex())
    iv = b"\x00" * BLOCK_SIZE
    cipher = AES.new(aesKey, AES.MODE_CBC, iv)
    pGx = cipher.decrypt(pEncGx)
    print("pGx: " + pGx.hex())
    bnPGx = int(pGx.hex(), 16)
    bnPrime = int(keys.prime, 16)
    bnPrivateKey = int(keys.privateKey, 16)
    secret = bytes.fromhex(
        hex(pow(bnPGx, bnPrivateKey, bnPrime)).rstrip("L").lstrip("0x")
    )
    print("secret: " + secret.hex())
    dataHash2 = data[
        USER_ID_POS
        + userIdLen
        + GX_SIZE : USER_ID_POS
        + userIdLen
        + GX_SIZE
        + SHA_DIGEST_LENGTH
    ]
    print("hash2: " + dataHash2.hex())
    secret2 = userId + secret
    print("secret2: " + secret2.hex())
    sha1 = hashlib.sha1()
    sha1.update(secret2)
    dataHash3 = sha1.digest()
    print("hash3: " + dataHash3.hex())
    if dataHash2 != dataHash3:
        print("Pin error!!!")
        return False
    print("Pin OK :)\n")
    flagPos = userIdLen + USER_ID_POS + GX_SIZE + SHA_DIGEST_LENGTH
    if ord(data[flagPos : flagPos + 1]):
        print("First flag error!!!")
        return False
    flagPos = userIdLen + USER_ID_POS + GX_SIZE + SHA_DIGEST_LENGTH
    if struct.unpack(">I", data[flagPos + 1 : flagPos + 5])[0]:
        print("Second flag error!!!")
        return False
    sha1 = hashlib.sha1()
    sha1.update(dest)
    dest_hash = sha1.digest()
    print("dest_hash: " + dest_hash.hex())
    finalBuffer = (
        userId + gUserId.encode("utf-8") + pGx + bytes.fromhex(keys.publicKey) + secret
    )
    sha1 = hashlib.sha1()
    sha1.update(finalBuffer)
    SKPrime = sha1.digest()
    print("SKPrime: " + SKPrime.hex())
    sha1 = hashlib.sha1()
    sha1.update(SKPrime + b"\x00")
    SKPrimeHash = sha1.digest()
    print("SKPrimeHash: " + SKPrimeHash.hex())
    ctx = applySamyGOKeyTransform(SKPrimeHash[:16])
    return {"ctx": ctx, "SKPrime": SKPrime}


def generateServerAcknowledge(SKPrime):
    sha1 = hashlib.sha1()
    sha1.update(SKPrime + b"\x01")
    SKPrimeHash = sha1.digest()
    return "0103000000000000000014" + SKPrimeHash.hex().upper() + "0000000000"


def parseClientAcknowledge(clientAck, SKPrime):
    sha1 = hashlib.sha1()
    sha1.update(SKPrime + b"\x02")
    SKPrimeHash = sha1.digest()
    tmpClientAck = "0104000000000000000014" + SKPrimeHash.hex().upper() + "0000000000"
    return clientAck == tmpClientAck
