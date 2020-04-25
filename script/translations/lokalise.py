"""API for Lokalise."""
from pprint import pprint

import requests

from .util import get_lokalise_token


def get_api(project_id, debug=False) -> "Lokalise":
    """Get Lokalise API."""
    return Lokalise(project_id, get_lokalise_token(), debug)


class Lokalise:
    """Lokalise API."""

    def __init__(self, project_id, token, debug):
        """Initialize Lokalise API."""
        self.project_id = project_id
        self.token = token
        self.debug = debug

    def request(self, method, path, data):
        """Make a request to the Lokalise API."""
        method = method.upper()
        kwargs = {"headers": {"x-api-token": self.token}}
        if method == "GET":
            kwargs["params"] = data
        else:
            kwargs["json"] = data

        if self.debug:
            print(method, f"{self.project_id}/{path}", data)

        req = requests.request(
            method,
            f"https://api.lokalise.com/api2/projects/{self.project_id}/{path}",
            **kwargs,
        )
        req.raise_for_status()

        if self.debug:
            pprint(req.json())
            print()

        return req.json()

    def keys_list(self, params={}):
        """List keys.

        https://app.lokalise.com/api2docs/curl/#transition-list-all-keys-get
        """
        return self.request("GET", "keys", params)["keys"]

    def keys_create(self, keys):
        """Create keys.

        https://app.lokalise.com/api2docs/curl/#transition-create-keys-post
        """
        return self.request("POST", "keys", {"keys": keys})["keys"]

    def keys_delete_multiple(self, key_ids):
        """Delete multiple keys.

        https://app.lokalise.com/api2docs/curl/#transition-delete-multiple-keys-delete
        """
        return self.request("DELETE", "keys", {"keys": key_ids})

    def keys_bulk_update(self, updates):
        """Update multiple keys.

        https://app.lokalise.com/api2docs/curl/#transition-bulk-update-put
        """
        return self.request("PUT", "keys", {"keys": updates})["keys"]

    def translations_list(self, params={}):
        """List translations.

        https://app.lokalise.com/api2docs/curl/#transition-list-all-translations-get
        """
        return self.request("GET", "translations", params)["translations"]

    def languages_list(self, params={}):
        """List languages.

        https://app.lokalise.com/api2docs/curl/#transition-list-project-languages-get
        """
        return self.request("GET", "languages", params)["languages"]
