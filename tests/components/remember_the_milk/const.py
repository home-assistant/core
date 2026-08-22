"""Constants for remember_the_milk tests."""

import json

PROFILE = "myprofile"
CREATE_ENTRY_DATA = {
    "api_key": "test-api-key",
    "shared_secret": "test-secret",
    "token": "test-token",
    "username": PROFILE,
}
TOKEN_RESPONSE = {
    "token": "test-token",
    "perms": "delete",
    "user": {"id": "1234567", "username": PROFILE, "fullname": "John Smith"},
}

# The legacy configuration file format:
LEGACY_JSON_STRING = json.dumps(
    {
        PROFILE: {
            "token": "mytoken",
            "id_map": {"123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}},
        }
    }
)

# The new configuration file format:
JSON_STRING = json.dumps(
    {
        PROFILE: {
            "id_map": {"123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}},
        }
    }
)
