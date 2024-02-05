"""Constants for the Yeelock integration."""

from homeassistant.const import Platform

DOMAIN = "yeelock"

PLATFORMS: list[str] = [
    Platform.LOCK,
]

CONF_PHONE = "phone"

UUID_BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
UUID_COMMAND = "58af3dca-6fc0-4fa3-9464-74662f043a3b"
UUID_NOTIFY = "58af3dca-6fc0-4fa3-9464-74662f043a3a"

LOCKER_KIND = {
    "lock": "02",
    "unlock": "01",
    "unlock_quick": "00",
}
