\"\"\"
Sovereign Network Architecture - Chinese IoT Hardware Definitions.
Maps device classifications for Tuya, Aqara, Xiaomi, Gree, and Midea.
\"\"\"
import logging

_LOGGER = logging.getLogger("homeassistant.components.sovereign_perimeter.zha_chinese")

class ChineseIoTRegistry:
    def __init__(self):
        self.supported_vendors = ["Tuya", "Aqara", "Xiaomi", "Gree", "Midea", "Loock", "Ecovacs"]

    def extract_vendor_profile(self, model_string: str) -> dict:
        \"\"\"Identifies radio interface profiles to isolate cellular vs local paths.\"\"\"
        if "智能锁" in model_string or "lock" in model_string.lower():
            return {"vendor": "Loock", "transport": "NB-IoT", "auth": "SIM-Crypt"}
        if "空调" in model_string or "ac" in model_string.lower():
            return {"vendor": "Gree", "transport": "WiFi-2.4G", "auth": "Local-Token"}
        return {"vendor": "Generic", "transport": "WiFi-2.4G", "auth": "Default"}
