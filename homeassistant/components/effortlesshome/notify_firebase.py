import logging
import json
import aiohttp
import asyncio
from homeassistant.components.notify import BaseNotificationService, ATTR_TITLE, ATTR_MESSAGE
from homeassistant.helpers import storage

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "effortlesshome_firebase_tokens"
STORAGE_VERSION = 1

FIREBASE_URL = "https://fcm.googleapis.com/v1/projects/effortlesshome-oauth/messages:send"

async def async_get_service(hass, config, discovery_info=None):
    service_account = hass.config.path(
        "custom_components/effortlesshome/firebase_service_account.json"
    )
    with open(service_account, "r") as f:
        creds = json.load(f)

    store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    tokens = await store.async_load() or []

    return EffortlessHomeFirebaseNotifyService(hass, creds, tokens, store)

class EffortlessHomeFirebaseNotifyService(BaseNotificationService):
    def __init__(self, hass, creds, tokens, store):
        self.hass = hass
        self.creds = creds
        self.tokens = tokens
        self.store = store
        self._access_token = None

    async def send_message(self, message="", **kwargs):
        title = kwargs.get(ATTR_TITLE, "EffortlessHome")
        if not self.tokens:
            _LOGGER.warning("No registered FCM tokens")
            return

        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        for fcm_token in self.tokens:
            payload = {
                "message": {
                    "token": fcm_token,
                    "notification": {"title": title, "body": message},
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(FIREBASE_URL, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        _LOGGER.error("Firebase push failed: %s", text)

    async def _get_access_token(self):
        # Use OAuth2 JWT flow manually
        import jwt
        import time
        import aiohttp

        now = int(time.time())
        payload = {
            "iss": self.creds["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }

        assertion = jwt.encode(payload, self.creds["private_key"], algorithm="RS256")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            ) as resp:
                result = await resp.json()
                return result["access_token"]

    async def register_token(self, token):
        if token not in self.tokens:
            self.tokens.append(token)
            await self.store.async_save(self.tokens)
