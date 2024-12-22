"""Define common test values."""

PAYLOAD_CONFIG = """
{
    "app": "abc",
    "devices": [{
        "id": "UL1",
        "ip": "192.168.1.123",
        "mac": "001122334455",
        "name": "",
        "serialNr": "000001",
        "type": "Qbus",
        "version": "3.14.0",
        "properties": {
            "connectable": {
                "read": true,
                "type": "boolean",
                "write": false
            },
            "connected": {
                "read": true,
                "type": "boolean",
                "write": false
            }
        },
        "functionBlocks": [{
            "id": "UL10",
            "location": "Living",
            "locationId": 0,
            "name": "LIVING",
            "originalName": "LIVING",
            "refId": "000001/10",
            "type": "onoff",
            "variant": [
                null
            ],
            "actions": {
                "off": null,
                "on": null
            },
            "properties": {
                "value": {
                    "read": true,
                    "type": "boolean",
                    "write": true
                }
            }
        }]
    }]
}"""

TOPIC_CONFIG = "cloudapp/QBUSMQTTGW/config"
