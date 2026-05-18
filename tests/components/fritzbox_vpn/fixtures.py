"""Shared test data for FritzBox VPN tests."""

MOCK_HOST = "192.168.178.1"
MOCK_USERNAME = "ha-user"
MOCK_PASSWORD = "secret"

MOCK_VPN_CONNECTIONS = {
    "conn-abc": {
        "uid": "wg-1",
        "name": "Office VPN",
        "active": True,
        "connected": False,
    },
    "conn-def": {
        "uid": "wg-2",
        "name": "Guest VPN",
        "active": False,
        "connected": False,
    },
}

LOGIN_XML_CHALLENGE = """<?xml version="1.0" encoding="utf-8"?>
<SessionInfo>
  <Challenge>12345</Challenge>
</SessionInfo>"""

LOGIN_XML_SID = """<?xml version="1.0" encoding="utf-8"?>
<SessionInfo>
  <SID>deadbeef</SID>
</SessionInfo>"""

MOCK_DATA_LUA_JSON = {
    "data": {
        "init": {
            "boxConnections": {
                "conn-abc": {
                    "uid": "conn-abc",
                    "name": "Office VPN",
                    "active": 1,
                    "connected": 0,
                }
            }
        }
    }
}
