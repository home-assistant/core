"""Mock data for the Home Assistant Upgrade Check integration.

Without a Supervisor there is no core update to check against. These let
anyone see the check in action; remove this module and its "Mock:" uses once
the check is tried and tested.
"""

MOCK_CORE_UPDATE_ID = "mock_core"
MOCK_RUNNING = "2026.7.0"
MOCK_TARGET = "2026.11.0"
MOCK_RELEASE_URL = "https://www.home-assistant.io/blog/2026/11/04/release-202611/"

# Added to the installed integrations so every category has content.
MOCK_DOMAINS = frozenset(
    {
        "mqtt",  # breaking
        "telegram_bot",  # breaking
        "unifi",  # breaking + noteworthy
        "proxmoxve",  # breaking + noteworthy + quality scale
        "rejseplanen",  # breaking + quality scale
        "matter",  # noteworthy
        "esphome",  # noteworthy
        "zwave_js",  # noteworthy
        "hue",  # noteworthy
        "airly",  # quality scale
        "etherscan",  # removed
    }
)
