"""Integrations exempt from the raw HTTP request check.

These integrations already made requests or created a client session with
``requests``, ``httpx`` or ``aiohttp`` directly before the
``hass-integration-raw-http-client`` check was introduced, so they are
grandfathered in to keep CI green. All device- and service-specific
communication should live in a library published on PyPI:
https://developers.home-assistant.io/docs/creating_component_code_review/#5-communication-with-devicesservices

This list must only ever shrink: do not add new domains. When an integration
is migrated to a library, remove it here so it stays enforced going forward.
"""

GRANDFATHERED_DOMAINS: frozenset[str] = frozenset(
    {
        "abode",
        "airos",
        "arest",
        "auth",
        "clickatell",
        "clicksend",
        "clicksend_tts",
        "currencylayer",
        "ddwrt",
        "downloader",
        "dublin_bus_transport",
        "facebook",
        "flume",
        "foursquare",
        "garadget",
        "go2rtc",
        "google_wifi",
        "haveibeenpwned",
        "hitron_coda",
        "huawei_lte",
        "ios",
        "itunes",
        "kankun",
        "linksys_smart",
        "llamalab_automate",
        "london_air",
        "mcp",
        "mjpeg",
        "nfandroidtv",
        "octoprint",
        "ohmconnect",
        "openhardwaremonitor",
        "plex",
        "pushsafer",
        "rainbird",
        "route53",
        "schluter",
        "sigfox",
        "signal_messenger",
        "synology_chat",
        "ted5000",
        "tomato",
        "uk_transport",
        "vodafone_station",
        "worldtidesinfo",
        "xiaomi",
        "xmpp",
        "zestimate",
    }
)
