"""Tests for the Thread integration."""

DATASET_1 = (
    "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_2 = (
    "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E486f6d65417373697374616e742101"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_3 = (
    "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E7ef09f90a3f09f90a5f09f90a47e01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)


ROUTER_DISCOVERY_GOOGLE_1 = {
    "type_": "_meshcop._udp.local.",
    "name": "Google-Nest-Hub-#ABED._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00|"],
    "port": 49191,
    "weight": 0,
    "priority": 0,
    "server": "2d99f293-cd8e-2770-8dd2-6675de9fa000.local.",
    "properties": {
        b"rv": b"1",
        b"vn": b"Google Inc.",
        b"mn": b"Google Nest Hub",
        b"nn": b"NEST-PAN-E1AF",
        b"xp": b"\x9eu\xe2V\xf6\x14\t\xa3",
        b"tv": b"1.3.0",
        b"xa": b"\xf6\xa9\x9bBZg\xab\xed",
        b"sb": b"\x00\x00\x01\xb1",
        b"at": b"\x00\x00b\xf2\xf8$T\xe3",
        b"pt": b"4\x860D",
        b"sq": b"{",
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
        b"id": b"\xbc7@\xc3\xe9c\xaa\x875\xbe\xbe\xcd|\xc5\x03\xc7",
        b"vat": b"000062f2f82454e3",
        b"vcd": b"BC3740C3E963AA8735BEBECD7CC503C7",
        b"vo": b"|\xd9\\",
        b"vvo": b"7CD95C",
        b"vxp": b"9e75e256f61409a3",
    },
    "interface_index": None,
}

ROUTER_DISCOVERY_GOOGLE_2 = {
    "type": "_meshcop._udp.local.",
    "name": "Google-Nest-Hub-#D8D5._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00q"],
    "port": 49191,
    "weight": 0,
    "priority": 0,
    "server": "80adee71-a563-2cfe-4402-95a9bc6ae3a1.local.",
    "properties": {
        b"rv": b"1",
        b"vn": b"Google Inc.",
        b"mn": b"Google Nest Hub",
        b"nn": b"NEST-PAN-E1AF",
        b"xp": b"\x9eu\xe2V\xf6\x14\t\xa3",
        b"tv": b"1.3.0",
        b"xa": b"\x8e9Z\xaek\xd5\xd8\xd5",
        b"sb": b"\x00\x00\x00\xb1",
        b"at": b"\x00\x00b\xf2\xf8$T\xe3",
        b"pt": b"4\x860D",
        b"sq": b'"',
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
        b"id": b"\xffi]\x11\xf6\xac)\xbe\xdb\x84\xb1o{\x8c\x1e\x82",
        b"vat": b"000062f2f82454e3",
        b"vcd": b"FF695D11F6AC29BEDB84B16F7B8C1E82",
        b"vo": b"|\xd9\\",
        b"vvo": b"7CD95C",
        b"vxp": b"9e75e256f61409a3",
    },
    "interface_index": None,
}

ROUTER_DISCOVERY_HASS = {
    "type_": "_meshcop._udp.local.",
    "name": "HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00s"],
    "port": 49153,
    "weight": 0,
    "priority": 0,
    "server": "core-silabs-multiprotocol.local.",
    "properties": {
        b"rv": b"1",
        b"vn": b"HomeAssistant",
        b"mn": b"OpenThreadBorderRouter",
        b"nn": b"OpenThread HC",
        b"xp": b"\xe6\x0f\xc7\xc1\x86!,\xe5",
        b"tv": b"1.3.0",
        b"xa": b"\xae\xeb/YKW\x0b\xbf",
        b"sb": b"\x00\x00\x01\xb1",
        b"at": b"\x00\x00\x00\x00\x00\x01\x00\x00",
        b"pt": b"\x8f\x06Q~",
        b"sq": b"3",
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
    },
    "interface_index": None,
}

ROUTER_DISCOVERY_HASS_BAD_DATA = {
    "type_": "_meshcop._udp.local.",
    "name": "HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00s"],
    "port": 49153,
    "weight": 0,
    "priority": 0,
    "server": "core-silabs-multiprotocol.local.",
    "properties": {
        b"rv": b"1",
        b"vn": b"HomeAssistant\xff",  # Invalid UTF-8
        b"mn": b"OpenThreadBorderRouter",
        b"nn": b"OpenThread HC",
        b"xp": b"\xe6\x0f\xc7\xc1\x86!,\xe5",
        b"tv": b"1.3.0",
        b"xa": b"\xae\xeb/YKW\x0b\xbf",
        b"sb": b"\x00\x00\x01\xb1",
        b"at": b"\x00\x00\x00\x00\x00\x01\x00\x00",
        b"pt": b"\x8f\x06Q~",
        b"sq": b"3",
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
    },
    "interface_index": None,
}

ROUTER_DISCOVERY_HASS_MISSING_DATA = {
    "type_": "_meshcop._udp.local.",
    "name": "HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00s"],
    "port": 49153,
    "weight": 0,
    "priority": 0,
    "server": "core-silabs-multiprotocol.local.",
    "properties": {
        b"rv": b"1",
        b"mn": b"OpenThreadBorderRouter",
        b"nn": b"OpenThread HC",
        b"xp": b"\xe6\x0f\xc7\xc1\x86!,\xe5",
        b"tv": b"1.3.0",
        b"xa": b"\xae\xeb/YKW\x0b\xbf",
        b"sb": b"\x00\x00\x01\xb1",
        b"at": b"\x00\x00\x00\x00\x00\x01\x00\x00",
        b"pt": b"\x8f\x06Q~",
        b"sq": b"3",
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
    },
    "interface_index": None,
}


ROUTER_DISCOVERY_HASS_MISSING_MANDATORY_DATA = {
    "type_": "_meshcop._udp.local.",
    "name": "HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    "addresses": [b"\xc0\xa8\x00s"],
    "port": 49153,
    "weight": 0,
    "priority": 0,
    "server": "core-silabs-multiprotocol.local.",
    "properties": {
        b"rv": b"1",
        b"vn": b"HomeAssistant",
        b"mn": b"OpenThreadBorderRouter",
        b"nn": b"OpenThread HC",
        b"xp": b"\xe6\x0f\xc7\xc1\x86!,\xe5",
        b"tv": b"1.3.0",
        b"sb": b"\x00\x00\x01\xb1",
        b"at": b"\x00\x00\x00\x00\x00\x01\x00\x00",
        b"pt": b"\x8f\x06Q~",
        b"sq": b"3",
        b"bb": b"\xf0\xbf",
        b"dn": b"DefaultDomain",
    },
    "interface_index": None,
}
