"""Common const used across tests for slide_local."""

from homeassistant.components.slide_local.const import DOMAIN

from tests.common import load_json_object_fixture

HOST = "127.0.0.2"
SLIDE_INFO_DATA = load_json_object_fixture("slide_1.json", DOMAIN)
