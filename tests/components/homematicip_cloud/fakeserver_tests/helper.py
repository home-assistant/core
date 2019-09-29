"""Helper for HomematicIP Cloud Tests."""
import json
from pathlib import Path

from homematicip.base.base_connection import (
    ATTR_CLIENT_AUTH,
    BaseConnection,
    HmipWrongHttpStatusError,
)
from homematicip_demo.fake_cloud_server import FakeCloudServer
from werkzeug.wrappers import Request, Response


def get_and_check_device_basics(hass, device_id, device_name, device_model):
    """Get and test basic device."""

    device = hass.states.get(device_id)
    assert device is not None
    assert device.attributes["model_type"] == device_model
    assert device.name == device_name
    return device


class AsyncConnectionLocal(BaseConnection):
    """
    Handles async http and websocket traffic without I/O.

    This is a replacement for AsyncHome to avoid I/O in tests.
    """

    connect_timeout = 20
    ping_timeout = 3
    ping_loop = 60

    def __init__(self, home_path=Path(__file__).parent.joinpath("json_data/home.json")):
        """Initialize local connection."""
        super().__init__()
        home_path = Path(__file__).parent.joinpath(home_path)
        self.local_cloud = FakeCloudServer(home_path)

        self.socket_connection = None  # ClientWebSocketResponse
        self.ws_reader_task = None
        self._ws_connected = False
        self.ping_pong_task = None
        # self.ws_close_lock = Lock()
        self._closing_task = None

    @property
    def ws_connected(self):
        """Websocket is connected."""
        return self._ws_connected

    async def init(self, accesspoint_id):
        """Init connection with accesspoint_id."""
        self.set_token_and_characteristics(accesspoint_id)

    def _restCall(self, path, body=None):
        """Shadows the original restCalls."""
        return path, body

    def full_url(self, partial_url):
        """Return full path url."""
        return "{}/hmip/{}".format(self._urlREST, partial_url)

    async def api_call(self, path, body=None, full_url=False):
        """Make the actual call to the HMIP server."""

        if not full_url:
            path = self.full_url(path)

        method_name = self._get_method_name(path)
        method_to_call = getattr(self.local_cloud, method_name)

        request = Request({})
        request.data = body
        request.headers = self.headers
        request.headers[ATTR_CLIENT_AUTH] = self.local_cloud.client_auth_token

        response = Response()
        response.content_type = "application/json;charset=UTF-8"

        result = method_to_call(request, response)

        if result.status == "200 OK":
            ret = None
            if result.content_type == "application/json;charset=UTF-8":
                result_str = result.data.decode("utf-8")
                if result_str == "":
                    ret = True
                else:
                    ret = json.loads(result_str)
            else:
                ret = True
            return ret
        else:
            raise HmipWrongHttpStatusError

    def _get_method_name(self, path: str):
        """Extract method name from url path."""
        path = path.replace("/", "_")
        return f"post{path}"

    async def ws_connect(self, *, on_message, on_error):
        """Fake method to connect websocket."""
        self._ws_connected = True

    async def close_websocket_connection(self, source_is_reading_loop=False):
        """Fake method to close websocket."""
        self._ws_connected = False
