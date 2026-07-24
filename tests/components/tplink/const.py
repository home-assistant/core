"""Constants for the tplink component tests."""

from kasa import (
    DeviceConfig,
    DeviceConnectionParameters,
    DeviceEncryptionType,
    DeviceFamily,
)

from homeassistant.components.tplink import (
    CONF_AES_KEYS,
    CONF_ALIAS,
    CONF_CAMERA_CREDENTIALS,
    CONF_CONNECTION_PARAMETERS,
    CONF_CREDENTIALS_HASH,
    CONF_HOST,
    CONF_LIVE_VIEW,
    CONF_MODEL,
    CONF_USES_HTTP,
    Credentials,
)

MODULE = "homeassistant.components.tplink"
MODULE_CONFIG_FLOW = "homeassistant.components.tplink.config_flow"
IP_ADDRESS = "127.0.0.1"
IP_ADDRESS2 = "127.0.0.2"
IP_ADDRESS3 = "127.0.0.3"
ALIAS = "My Bulb"
ALIAS_CAMERA = "My Camera"
MODEL = "HS100"
MODEL_CAMERA = "C210"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DEVICE_ID = "123456789ABCDEFGH"
DEVICE_ID_MAC = "AA:BB:CC:DD:EE:FF"
DHCP_FORMATTED_MAC_ADDRESS = MAC_ADDRESS.replace(":", "")
MAC_ADDRESS2 = "11:22:33:44:55:66"
MAC_ADDRESS3 = "66:55:44:33:22:11"
DEFAULT_ENTRY_TITLE = f"{ALIAS} {MODEL}"
DEFAULT_ENTRY_TITLE_CAMERA = f"{ALIAS_CAMERA} {MODEL_CAMERA}"
CREDENTIALS_HASH_LEGACY = ""
CONN_PARAMS_LEGACY = DeviceConnectionParameters(
    DeviceFamily.IotSmartPlugSwitch, DeviceEncryptionType.Xor
)
DEVICE_CONFIG_LEGACY = DeviceConfig(IP_ADDRESS)
DEVICE_CONFIG_DICT_LEGACY = {
    k: v for k, v in DEVICE_CONFIG_LEGACY.to_dict().items() if k != "credentials"
}
CREDENTIALS = Credentials("foo", "bar")
CREDENTIALS_HASH_AES = "AES/abcdefghijklmnopqrstuvabcdefghijklmnopqrstuv=="
CREDENTIALS_HASH_KLAP = "KLAP/abcdefghijklmnopqrstuv=="
CONN_PARAMS_KLAP = DeviceConnectionParameters(
    DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Klap
)
DEVICE_CONFIG_KLAP = DeviceConfig(
    IP_ADDRESS,
    credentials=CREDENTIALS,
    connection_type=CONN_PARAMS_KLAP,
)
CONN_PARAMS_AES = DeviceConnectionParameters(
    DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Aes
)
_test_privkey = (
    "MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKLJKmBWGj6WYo9sewI8vkqar"
    "Ed5H1JUr8Jj/LEWLTtV6+Mm4mfyEk6YKFHSmIG4AGgrVsGK/EbEkTZk9CwtixNQpBVc36oN2R"
    "vuWWV38YnP4vI63mNxTA/gQonCsahjN4HfwE87pM7O5z39aeunoYm6Be663t33DbJH1ZUbZjm"
    "tAgMBAAECgYB1Bn1KaFvRprcQOIJt51E9vNghQbf8rhj0fIEKpdC6mVhNIoUdCO+URNqnh+hP"
    "SQIx4QYreUlHbsSeABFxOQSDJm6/kqyQsp59nCVDo/bXTtlvcSJ/sU3riqJNxYqEU1iJ0xMvU"
    "N1VKKTmik89J8e5sN9R0AFfUSJIk7MpdOoD2QJBANTbV27nenyvbqee/ul4frdt2rrPGcGpcV"
    "QmY87qbbrZgqgL5LMHHD7T/v/I8D1wRog1sBz/AiZGcnv/ox8dHKsCQQDDx8DCGPySSVqKVua"
    "yUkBNpglN83wiCXZjyEtWIt+aB1A2n5ektE/o8oHnnOuvMdooxvtid7Mdapi2VLHV7VMHAkAE"
    "d0GjWwnv2cJpk+VnQpbuBEkFiFjS/loZWODZM4Pv2qZqHi3DL9AA5XPBLBcWQufH7dBvG06RP"
    "QMj5N4oRfUXAkEAuJJkVliqHNvM4OkGewzyFII4+WVYHNqg43dcFuuvtA27AJQ6qYtYXrvp3k"
    "phI3yzOIhHTNCea1goepSkR5ODFwJBAJCTRbB+P47aEr/xA51ZFHE6VefDBJG9yg6yK4jcOxg"
    "5ficXEpx8442okNtlzwa+QHpm/L3JOFrHwiEeVqXtiqY="
)
_test_pubkey = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCiySpgVho+lmKPbHsCPL5KmqxHeR9SVK/CY"
    "/yxFi07VevjJuJn8hJOmChR0piBuABoK1bBivxGxJE2ZPQsLYsTUKQVXN+qDdkb7llld/GJz+"
    "LyOt5jcUwP4EKJwrGoYzeB38BPO6TOzuc9/Wnrp6GJugXuut7d9w2yR9WVG2Y5rQIDAQAB"
)
AES_KEYS = {"private": _test_privkey, "public": _test_pubkey}
DEVICE_CONFIG_AES = DeviceConfig(
    IP_ADDRESS2,
    credentials=CREDENTIALS,
    connection_type=CONN_PARAMS_AES,
    aes_keys=AES_KEYS,
)
CONN_PARAMS_AES_CAMERA = DeviceConnectionParameters(
    DeviceFamily.SmartIpCamera, DeviceEncryptionType.Aes, https=True, login_version=2
)
DEVICE_CONFIG_AES_CAMERA = DeviceConfig(
    IP_ADDRESS3,
    credentials=CREDENTIALS,
    connection_type=CONN_PARAMS_AES_CAMERA,
)

DEVICE_CONFIG_DICT_KLAP = {
    k: v for k, v in DEVICE_CONFIG_KLAP.to_dict().items() if k != "credentials"
}
DEVICE_CONFIG_DICT_AES = {
    k: v for k, v in DEVICE_CONFIG_AES.to_dict().items() if k != "credentials"
}
CREATE_ENTRY_DATA_LEGACY = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_LEGACY.to_dict(),
    CONF_USES_HTTP: False,
}

CREATE_ENTRY_DATA_KLAP = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CREDENTIALS_HASH: CREDENTIALS_HASH_KLAP,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_KLAP.to_dict(),
    CONF_USES_HTTP: True,
}
CREATE_ENTRY_DATA_AES = {
    CONF_HOST: IP_ADDRESS2,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CREDENTIALS_HASH: CREDENTIALS_HASH_AES,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_AES.to_dict(),
    CONF_USES_HTTP: True,
    CONF_AES_KEYS: AES_KEYS,
}
CREATE_ENTRY_DATA_AES_CAMERA = {
    CONF_HOST: IP_ADDRESS3,
    CONF_ALIAS: ALIAS_CAMERA,
    CONF_MODEL: MODEL_CAMERA,
    CONF_CREDENTIALS_HASH: CREDENTIALS_HASH_AES,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_AES_CAMERA.to_dict(),
    CONF_USES_HTTP: True,
    CONF_LIVE_VIEW: True,
    CONF_CAMERA_CREDENTIALS: {"username": "camuser", "password": "campass"},
}
SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)
