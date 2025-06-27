"""Configuration for aqara tests."""
import json

import pytest
import requests

from tests.common import load_fixture

res_info = json.loads(load_fixture("res_info.json", "aqara"))


def get_open_api_response_content(req_data) -> str:
    """set_off_valuey."""
    query_res_value_count: int = 0
    query_res_name_count: int = 0

    req_data = json.loads(req_data)
    intent = req_data.get("intent", "")
    if intent == "query.device.info" and req_data["data"]["pageNum"] == 1:
        return str(load_fixture("device_info_1.json", "aqara").encode())
    elif intent == "query.device.info" and req_data["data"]["pageNum"] == 2:
        return str(load_fixture("device_info_2.json", "aqara").encode())
    elif intent == "query.resource.info":
        model = req_data["data"]["model"]
        return str(json.dumps(res_info.get(model, "")).encode())
    elif intent == "query.resource.name":  #
        if query_res_name_count == 0:
            query_res_name_count += 1
            return str(load_fixture("res_name_1.json", "aqara").encode())
        else:
            return str(load_fixture("res_name_2.json", "aqara").encode())
    elif intent == "query.resource.value":
        if query_res_value_count == 0:
            query_res_value_count += 1
            return str(load_fixture("res_value_1.json", "aqara").encode())
        else:
            return str(load_fixture("res_value_2.json", "aqara").encode())
    elif intent == "config.mqtt.add":
        return str(load_fixture("mqtt_info.json", "aqara").encode())
    elif intent == "query.position.info":
        if req_data["data"]["parentPositionId"] == "":
            return str(load_fixture("position_1.json", "aqara").encode())
        else:
            data = json.loads(load_fixture("position_2.json", "aqara"))
            return str(
                json.dumps(data.get(req_data["data"]["parentPositionId"])).encode()
            )
    elif intent == "query.scene.listByPositionId":
        data = json.loads(load_fixture("position_id.json", "aqara"))
        content = data.get(req_data["data"]["positionId"])
        return str(json.dumps(content).encode())

    return ""


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""

    def custom_matcher(request):
        if request.path_url == "/v3.0/open/authorize":
            resp = requests.Response()
            resp.status_code = 200
            resp._content = str(load_fixture("authorize.json", "aqara").encode())
            return resp
        elif request.path_url == "/v3.0/open/access_token":
            resp = requests.Response()
            resp.status_code = 200
            resp._content = str(load_fixture("token.json", "aqara").encode())
            return resp
        elif request.path_url == "/v3.0/open/api":
            resp = requests.Response()
            resp.status_code = 200
            content = str(get_open_api_response_content(request.text))
            resp._content = content
            return resp
        return

    requests_mock._adapter.add_matcher(custom_matcher)
