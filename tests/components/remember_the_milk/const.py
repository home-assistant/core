"""Constants for remember_the_milk tests."""

import json

PROFILE = "myprofile"
TOKEN = "mytoken"
JSON_STRING = json.dumps(
    {
        "myprofile": {
            "token": "mytoken",
            "id_map": {"1234": {"list_id": "0", "timeseries_id": "1", "task_id": "2"}},
        }
    }
)
