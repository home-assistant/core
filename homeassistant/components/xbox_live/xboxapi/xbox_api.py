"""Wrapper for http://xapi.us."""

import json

# -*- coding: utf-8 -*-
import requests

BASE_URL = "https://xapi.us"


class XboxApi:
    """Interacts with xapi.us service."""

    # XboxApi key
    api_key = ""

    def __init__(self, api_key):
        """Only requires the XboxApi key."""
        self.api_key = api_key

    def get_profile(self):
        """Return information for current token profile."""
        res = self.request(BASE_URL + "/v2/profile")
        return res.json()

    def get_xuid(self):
        """Return your xuid."""
        res = self.request(BASE_URL + "/v2/accountXuid")
        return res.json()

    def get_messages(self):
        """Return your messages."""
        res = self.request(BASE_URL + "/v2/messages")
        return res.json()

    def get_conversations(self):
        """Return your messages."""
        res = self.request(BASE_URL + "/v2/conversations")
        return res.json()

    def get_xuid_by_gamertag(self, gamertag):
        """Return XUID by gamertag."""
        res = self.request(BASE_URL + f"/v2/xuid/{gamertag}")
        return res.json()

    def get_gamertag_by_xuid(self, xuid):
        """Return gamertag by XUID."""
        res = self.request(BASE_URL + f"/v2/gamertag/{xuid}")
        return res.json()

    def get_user_profile(self, xuid):
        """Return profile by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/profile")
        return res.json()

    def get_user_gamercard(self, xuid):
        """Return gamercard by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/gamercard")
        return res.json()

    def get_user_presence(self, xuid):
        """Return current presence information by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/presence")
        return res.json()

    def get_user_activity(self, xuid):
        """Return current activity information by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/activity")
        return res.json()

    def get_user_activity_recent(self, xuid):
        """Return recent activity information by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/activity/recent")
        return res.json()

    def get_user_friends(self, xuid):
        """Return friends by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/friends")
        return res.json()

    def get_user_followers(self, xuid):
        """Return followers by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/followers")
        return res.json()

    def get_recent_players(self):
        """Return recent players by XUID."""
        res = self.request(BASE_URL + "/v2/recent-players")
        return res.json()

    def get_user_gameclips(self, xuid):
        """Return game clips by XUID."""
        res = self.request(BASE_URL + f"/v2/{xuid}/game-clips")
        return res.json()

    # continue with #16

    def send_message(self, message, xuids=None):
        """Send a message to a set of user(s)."""
        xuids = xuids or []
        headers = {"X-AUTH": self.api_key, "Content-Type": "application/json"}

        payload = {"message": message, "to": []}

        for xuid in xuids:
            payload["to"].append(xuid)

        res = requests.post(
            BASE_URL + "/v2/messages", headers=headers, data=json.dumps(payload)
        )
        res.json()

    def request(self, url):
        """Create an HTTP request."""
        headers = {"X-AUTH": self.api_key}
        res = requests.get(url, headers=headers)
        return res
