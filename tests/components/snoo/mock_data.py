"""Mock data for Snoo testing."""

from python_snoo.containers import SnooDevice

MOCK_AMAZON_AUTH = {
    # This is a JWT with random values.
    "AccessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTQ3ODktOTBhYi1jZGVmMDEyMzQ1NjciLCJpc3MiOiJodHRwczovL2NvZ25pdG8taWRwLnVzLXdlc3QtMi5hbWF6b25hd3MuY29tL3VzLXdlc3QtMl9FeGFtcGxlVXNlclBvb2xJZCIsImNsaWVudF9pZCI6ImFiY2RlZmdoMTIzNDU2Nzg5MGFiY2RlZmdoMTIiLCJvcmlnaW5fanRpIjoiYjhkOWUwZjEtMmczaC00aTVqLTZrN2wtOG05bjBvMXAycTNyIiwiZXZlbnRfaWQiOiJmMGcxaDJpMy00ajVrLTZsN20tOG45by0wcDFxMnIzczR0NXUiLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJzY29wZSI6ImF3cy5jb2duaXRvLnNpZ25pbi51c2VyLmFkbWluIiwiYXV0aF90aW1lIjoxNzAwMDAwMDAwLCJleHAiOjE3MDAwMDM2MDAsImlhdCI6MTcwMDAwMDAwMCwianRpIjoidjZ3N3g4eTktMHoxYS0yYjNjLTRkNWUtNmY3ZzhoOWkwajFrIiwidXNlcm5hbWUiOiIxMjNlNDU2Ny1lODliLTEyZDMtYTQ1Ni00MjY2MTQxNzQwMDAifQ.zH5vy5itWot_5-rdJgYoygeKx696Uge46zxXMhdn5RE",
    "IdToken": "random_id",
    "RefreshToken": "refresh_token",
}

MOCK_SNOO_AUTH = {"expiresIn": 10800, "snoo": {"token": "random_snoo_token"}}


MOCK_SNOO_DEVICES = [
    SnooDevice(
        serialNumber="random_num",
        deviceType=1,
        firmwareVersion="1.0",
        babyIds=["35235-211235-dfasdf-32523"],
        name="Test Snoo",
        presence={},
        presenceIoT={},
        awsIoT={},
        lastSSID={},
        provisionedAt="random_time",
    )
]
