"""API for Lokalise."""
import requests


class Lokalise:
    """Lokalise API."""

    def __init__(self, project_id, token):
        """Initialize Lokalise API."""
        self.project_id = project_id
        self.token = token

    def request(self, method, path, data):
        """Make a request to the Lokalise API."""
        method = method.upper()
        kwargs = {"headers": {"x-api-token": self.token}}
        if method == "GET":
            kwargs["params"] = data
        else:
            kwargs["json"] = data

        req = requests.request(
            method,
            f"https://api.lokalise.com/api2/projects/{self.project_id}/{path}",
            **kwargs,
        )
        req.raise_for_status()
        return req.json()

    def keys_list(self, params={}):
        """Fetch key ID from a name.

        https://app.lokalise.com/api2docs/curl/#transition-list-all-keys-get
        """
        return self.request("GET", "keys", params)["keys"]

    def keys_delete_multiple(self, key_ids):
        """Delete multiple keys.

        https://app.lokalise.com/api2docs/curl/#transition-delete-multiple-keys-delete
        """
        return self.request("DELETE", "keys", {"keys": key_ids})
