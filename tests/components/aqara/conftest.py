"""Configuration for aqara tests."""
import json
import pytest
import requests
from tests.common import load_fixture
import aqara_iot.openmq
from .common import mock_start

res_info = json.loads(load_fixture("res_info.json", "aqara"))
query_res_value_count: int = 0
query_res_name_count: int = 0
query_device_info_count: int = 0


def get_open_api_response_content(req_data) -> str:
    global query_res_value_count
    global query_res_name_count
    global query_device_info_count

    req_data = json.loads(req_data)
    intent = req_data.get("intent", "")
    # print("+++++++++++req_data+++++++:", intent)
    if intent == "query.device.info" and req_data["data"]["pageNum"] == 1:
        # {'intent': 'query.device.info', 'data': {'dids': [], 'positionId': '', 'pageNum': 1, 'pageSize': 81}}
        return load_fixture("device_info_1.json", "aqara").encode()
    elif intent == "query.device.info" and req_data["data"]["pageNum"] == 2:
        # {'intent': 'query.device.info', 'data': {'dids': [], 'positionId': '', 'pageNum': 2, 'pageSize': 81}}
        return load_fixture("device_info_2.json", "aqara").encode()
    elif intent == "query.resource.info":
        # {'intent': 'query.resource.info', 'data': {'model': 'lumi.sensor_motion.v2', 'resourceId': ''}}
        model = req_data["data"]["model"]
        return json.dumps(res_info.get(model, "")).encode()
    elif intent == "query.resource.name":  #
        if query_res_name_count == 0:
            query_res_name_count += 1
            return load_fixture("res_name_1.json", "aqara").encode()
        else:
            return load_fixture("res_name_2.json", "aqara").encode()
    elif intent == "query.resource.value":
        if query_res_value_count == 0:
            query_res_value_count += 1
            return load_fixture("res_value_1.json", "aqara").encode()
        else:
            return load_fixture("res_value_2.json", "aqara").encode()
    elif intent == "config.mqtt.add":
        print("===xxxxxxxxx===mqtt_info:")
        return load_fixture("mqtt_info.json", "aqara").encode()
    elif intent == "query.position.info":
        if req_data["data"]["parentPositionId"] == "":
            # {'intent': 'query.position.info', 'data': {'parentPositionId': '', 'pageNum': 1, 'pageSize': 50}}
            return load_fixture("position_1.json", "aqara").encode()
        else:
            data = json.loads(load_fixture("position_2.json", "aqara"))
            return json.dumps(data.get(req_data["data"]["parentPositionId"])).encode()
    elif intent == "query.scene.listByPositionId":
        # {'intent': 'query.scene.listByPositionId', 'data': {'positionId': 'real1.743791439074398208', 'pageNum': 1, 'pageSize': 50}}
        # print("===xxxxxxxxx===query.scene. listByPositionId :", req_data)
        data = json.loads(load_fixture("position_id.json", "aqara"))
        content = data.get(req_data["data"]["positionId"])
        return json.dumps(content).encode()

    print("============error no handle=========:", req_data)
    return ""


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""
    # print(load_fixture("authorize.json", "aqara"))

    def custom_matcher(request):
        if request.path_url == "/v3.0/open/authorize":
            resp = requests.Response()
            resp.status_code = 200
            resp._content = load_fixture("authorize.json", "aqara").encode()
            return resp
        elif request.path_url == "/v3.0/open/access_token":
            resp = requests.Response()
            resp.status_code = 200
            resp._content = load_fixture("token.json", "aqara").encode()
            return resp
        elif request.path_url == "/v3.0/open/api":
            resp = requests.Response()
            resp.status_code = 200
            content = get_open_api_response_content(request.text)  # .encode()
            # if len(content) == 0:
            #     print(
            #         "kkkkkkkkkkkkkkkkkkkkkkkkkkk   error kkkkkkkkkkkkkkkkkkkk"
            #     )
            resp._content = content
            return resp
        return

    requests_mock._adapter.add_matcher(custom_matcher)
