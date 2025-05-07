"""Snoo constants for testing."""

import time

from python_snoo.containers import AuthorizationInfo, SnooData

MOCK_AMAZON_AUTH = {
    # This is a JWT with random values.
    "AccessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2"
    "LTQ3ODktOTBhYi1jZGVmMDEyMzQ1NjciLCJpc3MiOiJodHRwczovL2NvZ25pdG8taWRwLnVzLXdlc3Qt"
    "Mi5hbWF6b25hd3MuY29tL3VzLXdlc3QtMl9FeGFtcGxlVXNlclBvb2xJZCIsImNsaWVudF9pZCI6ImFiY"
    "2RlZmdoMTIzNDU2Nzg5MGFiY2RlZmdoMTIiLCJvcmlnaW5fanRpIjoiYjhkOWUwZjEtMmczaC00aTVqLT"
    "ZrN2wtOG05bjBvMXAycTNyIiwiZXZlbnRfaWQiOiJmMGcxaDJpMy00ajVrLTZsN20tOG45by0wcDFxMnI"
    "zczR0NXUiLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJzY29wZSI6ImF3cy5jb2duaXRvLnNpZ25pbi51c2Vy"
    "LmFkbWluIiwiYXV0aF90aW1lIjoxNzAwMDAwMDAwLCJleHAiOjE3MDAwMDM2MDAsImlhdCI6MTcwMDAwM"
    "DAwMCwianRpIjoidjZ3N3g4eTktMHoxYS0yYjNjLTRkNWUtNmY3ZzhoOWkwajFrIiwidXNlcm5hbWUiOi"
    "IxMjNlNDU2Ny1lODliLTEyZDMtYTQ1Ni00MjY2MTQxNzQwMDAifQ.zH5vy5itWot_5-rdJgYoygeKx696"
    "Uge46zxXMhdn5RE",
    "IdToken": "random_id",
    "RefreshToken": "refresh_token",
}

MOCK_SNOO_AUTH = {"expiresIn": 10800, "snoo": {"token": "random_snoo_token"}}

MOCK_SNOO_DEVICES = [
    {
        "serialNumber": "random_num",
        "deviceType": 1,
        "firmwareVersion": 1.0,
        "babyIds": ["35235-211235-dfasdf-32523"],
        "name": "Test Snoo",
        "presence": {},
        "presenceIoT": {},
        "awsIoT": {},
        "lastSSID": {},
        "provisionedAt": "random_time",
    }
]

MOCK_SNOO_DATA = SnooData.from_dict(
    {
        "system_state": "normal",
        "sw_version": "v1.14.27",
        "state_machine": {
            "session_id": "0",
            "state": "ONLINE",
            "is_active_session": "false",
            "since_session_start_ms": -1,
            "time_left": -1,
            "hold": "off",
            "weaning": "off",
            "audio": "on",
            "up_transition": "NONE",
            "down_transition": "NONE",
            "sticky_white_noise": "off",
        },
        "left_safety_clip": 1,
        "right_safety_clip": 1,
        "event": "status_requested",
        "event_time_ms": int(time.time()),
        "rx_signal": {"rssi": -45, "strength": 100},
    }
)


MOCKED_AUTH = AuthorizationInfo(
    snoo=MOCK_SNOO_AUTH,
    aws_access=MOCK_AMAZON_AUTH["AccessToken"],
    aws_id=MOCK_AMAZON_AUTH["IdToken"],
    aws_refresh=MOCK_AMAZON_AUTH["RefreshToken"],
)
