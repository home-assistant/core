"""Constants for remember_the_milk tests."""

import json

PROFILE = "myprofile"
CONFIG = {
    "name": f"{PROFILE}",
    "api_key": "test-api-key",
    "shared_secret": "test-shared-secret",
}
TOKEN = "mytoken"
JSON_STRING = json.dumps(
    {
        "myprofile": {
            "token": "mytoken",
            "id_map": {"123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}},
        }
    }
)
