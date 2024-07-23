"""Tests for the Elmax component."""

from tests.common import load_fixture

MOCK_USER_JWT = (
    "JWT eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJfaWQiOiIxYjExYmIxMWJiYjExMTExYjFiMTFiMWIiLCJlbWFpbCI6InRoaXMuaXNAdGVzdC5jb20iLCJyb2xlIjoid"
    "XNlciIsImlhdCI6MTYzNjE5OTk5OCwiZXhwIjoxNjM2MjM1OTk4fQ.1C7lXuKyX1HEGOfMxNwxJ2n-CjoW4rwvNRITQxLI"
    "Cv0"
)
MOCK_USERNAME = "this.is@test.com"
MOCK_USER_ROLE = "user"
MOCK_USER_ID = "1b11bb11bbb11111b1b11b1b"
MOCK_PANEL_ID = "2db3dae30b9102de4d078706f94d0708"
MOCK_PANEL_NAME = "Test Panel Name"
MOCK_PANEL_PIN = "000000"
MOCK_WRONG_PANEL_PIN = "000000"
MOCK_PASSWORD = "password"
MOCK_DIRECT_HOST = "1.1.1.1"
MOCK_DIRECT_HOST_CHANGED = "2.2.2.2"
MOCK_DIRECT_PORT = 443
MOCK_DIRECT_SSL = True
MOCK_DIRECT_CERT = load_fixture("direct/cert.pem", "elmax")
MOCK_DIRECT_FOLLOW_MDNS = True
