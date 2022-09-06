"""General Starlink patchers."""
from unittest.mock import patch

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)
