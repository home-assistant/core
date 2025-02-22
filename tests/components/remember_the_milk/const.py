"""Constants for remember_the_milk tests."""

import json

PROFILE = "myprofile"
TOKEN = "mytoken"
STORED_DATA = {
    "myprofile": {
        "token": "mytoken",
        "id_map": {"123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}},
    }
}
JSON_STRING = json.dumps(STORED_DATA)
