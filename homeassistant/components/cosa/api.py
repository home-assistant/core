"""The API client for interacting with the Cosa service."""

from datetime import UTC, datetime
import http.client
import json


class Api:
    """The API client for interacting with the Cosa service."""

    __apiUri = "kiwi.cosa.com.tr"
    __username = None
    __password = None
    __authToken = None

    __lastSuccessfulCall = None

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client with username and password."""
        self.__username = username
        self.__password = password

    def __getHeaders(self):
        """Get the headers for the API request."""
        headers = {"Content-Type": "application/json"}

        if self.hasAuth():
            headers["authToken"] = self.__authToken

        return headers

    def getConnection(self) -> http.client.HTTPSConnection:
        """Get a connection to the Cosa service."""
        return http.client.HTTPSConnection(self.__apiUri)

    def status(self) -> bool:
        """Check the status of the API client."""
        if (
            self.__lastSuccessfulCall is None
            or datetime.now(datetime.timezone.utc) - self.__lastSuccessfulCall
        ) and not self.login():
            return False

        return True

    # region Login

    def login(self) -> bool:
        """Log in to the Cosa service and obtain an authentication token."""
        payload = {"email": self.__username, "password": self.__password}

        data = self.__postWithoutAuth("/api/users/login", payload)

        if data is not None and "authToken" in data:
            self.__authToken = data["authToken"]
            return True

        self.__authToken = None
        return False

    def hasAuth(self):
        """Check if the API client has an authentication token."""
        return self.__authToken is not None

    # endregion

    def getEndpoints(self) -> dict | None:
        """Retrieve the list of endpoints from the Cosa service."""
        data = self.__get("/api/endpoints/getEndpoints")

        if data is not None and "endpoints" in data:
            return data["endpoints"]

        return None

    def getEndpoint(self, endpointId: str) -> dict | None:
        """Retrieve details of a specific endpoint from the Cosa service."""
        payload = {"endpoint": endpointId}

        data = self.__post("/api/endpoints/getEndpoint", payload)

        if data is not None and "endpoint" in data:
            return data["endpoint"]

        return None

    def setTargetTemperatures(
        self,
        endpointId: str,
        homeTemp: int,
        awayTemp: int,
        sleepTemp: int,
        customTemp: int,
    ) -> bool:
        """Set the target temperatures for a specific endpoint."""
        payload = {
            "endpoint": endpointId,
            "targetTemperatures": {
                "home": homeTemp,
                "away": awayTemp,
                "sleep": sleepTemp,
                "custom": customTemp,
            },
        }

        data = self.__post("/api/endpoints/setTargetTemperatures", payload)

        if data is not None:
            return True

        return False

    def disable(self, endpointId: str) -> bool:
        """Disable the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "manual", "option": "frozen"}

        data = self.__post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    def enableSchedule(self, endpointId: str) -> bool:
        """Enable the schedule mode for the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "schedule"}

        data = self.__post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    def enableCustomMode(self, endpointId: str) -> bool:
        """Enable the custom mode for the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "manual", "option": "custom"}

        data = self.__post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    # region Private Call Implementations

    def __post(
        self, endpoint: str, payload: dict, allowRetry: bool = True
    ) -> dict | None:
        if not self.hasAuth() and not self.login():
            return None

        return self.__postWithoutAuth(endpoint, payload, allowRetry)

    def __postWithoutAuth(
        self, endpoint: str, payload: dict, allowRetry: bool = True
    ) -> dict | None:
        payload = json.dumps(payload)
        headers = self.__getHeaders()
        conn = self.getConnection()

        try:
            conn.request("POST", endpoint, payload, headers)
            res = conn.getresponse()
        except (http.client.HTTPException, json.JSONDecodeError):
            if allowRetry:
                return self.__post(endpoint, payload, False)

            return None

        return self.getResponseIfSuccess(res)

    def __get(self, endpoint: str, allowRetry: bool = True) -> dict | None:
        if not self.hasAuth() and not self.login():
            return None

        return self.__getWithoutAuth(endpoint, allowRetry)

    def __getWithoutAuth(self, endpoint: str, allowRetry: bool = True) -> dict | None:
        headers = self.__getHeaders()
        conn = self.getConnection()

        try:
            conn.request("GET", endpoint, None, headers)
            res = conn.getresponse()
        except (http.client.HTTPException, json.JSONDecodeError):
            if allowRetry:
                return self.__get(endpoint, False)

            return None

        return self.getResponseIfSuccess(res)

    def getResponseIfSuccess(self, response: http.client.HTTPResponse) -> dict | None:
        """Check if the response is successful and return the data if it is.

        Args:
            response (http.client.HTTPResponse): The HTTP response object.

        Returns:
            Optional[dict]: The response data if successful, otherwise None.

        """
        if response.status != 200:
            return None

        data = json.loads(response.read())

        if "ok" in data and data["ok"] == 1:
            self.__lastSuccessfulCall = datetime.now(UTC)
            return data

        return None


# endregion
