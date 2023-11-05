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
    "user": {"id": "1234567", "username": "johnsmith", "fullname": "John Smith"},
}

# The legacy configuration file format:

#  {
#    "myprofile": {
#      "token": "mytoken",
#      "id_map": {"123": {"list_id": 1, "timeseries_id": 2, "task_id": 3}},
#    }
#  }

# The new configuration file format:
JSON_STRING = json.dumps(
    {
        "myprofile": {
            "id_map": {"123": {"list_id": 1, "timeseries_id": 2, "task_id": 3}},
        }
    }
)
