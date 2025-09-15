"""Constants for the Uptime Kuma integration."""

from pythonkuma import MonitorType

DOMAIN = "uptime_kuma"

HAS_CERT = {
    MonitorType.HTTP,
    MonitorType.KEYWORD,
    MonitorType.JSON_QUERY,
}
HAS_URL = HAS_CERT | {MonitorType.REAL_BROWSER}
HAS_PORT = {
    MonitorType.PORT,
    MonitorType.STEAM,
    MonitorType.GAMEDIG,
    MonitorType.MQTT,
    MonitorType.RADIUS,
    MonitorType.SNMP,
    MonitorType.SMTP,
}
HAS_HOST = HAS_PORT | {
    MonitorType.PING,
    MonitorType.TAILSCALE_PING,
    MonitorType.DNS,
}
