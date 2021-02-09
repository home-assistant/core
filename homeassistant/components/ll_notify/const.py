"""Constants."""
from pathlib import Path

DOMAIN = "ll_notify"
WS_TYPE_MESSAGE = f"{DOMAIN}/message"

SCRIPT_FILENAME = "ll_notify.js"
FRONTEND_SCRIPT_URL = f"/{SCRIPT_FILENAME}"
DATA_EXTRA_MODULE_URL = "frontend_extra_module_url"
VIEW_NAME = f"{DOMAIN}_script"
CUSTOM_COMPONENT_DIR = f"custom_components/{DOMAIN}"
SCRIPT_PATH = Path(__file__).parent / "js" / "dist" / SCRIPT_FILENAME
