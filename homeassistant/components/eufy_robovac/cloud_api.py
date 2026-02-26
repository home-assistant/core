"""Cloud discovery helpers for Eufy RoboVac onboarding.

This module is intentionally scoped for config-flow onboarding only:
it logs in to Eufy, resolves RoboVac devices on the account, and fetches
Tuya local keys needed for local control.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import md5, sha256
import hmac
import json
import logging
import math
import random
import string
import time
from typing import Any
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import requests

_EUFY_HEADERS = {
    "User-Agent": "EufyHome-Android-2.4.0",
    "timezone": "Europe/London",
    "category": "Home",
    "token": "",
    "uid": "",
    "openudid": "sdk_gphone64_arm64",
    "clientType": "2",
    "language": "en",
    "country": "US",
    "Accept-Encoding": "gzip",
}

_EUFY_LOGIN_URL = "https://home-api.eufylife.com/v1/user/email/login"
_EUFY_LOGIN_AUTH = {
    "client_Secret": "GQCpr9dSp3uQpsOMgJ4xQ",
    "client_id": "eufyhome-app",
}

_TUYA_BASE_URL = {
    "AZ": "https://a1.tuyaus.com",
    "AY": "https://a1.tuyacn.com",
    "IN": "https://a1.tuyain.com",
    "EU": "https://a1.tuyaeu.com",
}
_TUYA_SIGNATURE_FIELDS = {
    "a",
    "v",
    "lat",
    "lon",
    "lang",
    "deviceId",
    "appVersion",
    "ttid",
    "isH5",
    "h5Token",
    "os",
    "clientId",
    "postData",
    "time",
    "requestId",
    "et",
    "n4h5",
    "sid",
    "sp",
}
_TUYA_HMAC_KEY = (
    "A_cepev5pfnhua4dkqkdpmnrdxx378mpjr_s8x78u7xwymasd9kqa7a73pjhxqsedaj".encode()
)
_TUYA_HEADERS = {"User-Agent": "TY-UA=APP/Android/2.4.0/SDK/null"}
_TUYA_PASSWORD_CIPHER = Cipher(
    algorithms.AES(
        bytearray(
            [36, 78, 109, 138, 86, 172, 135, 145, 36, 67, 45, 139, 108, 188, 162, 196]
        )
    ),
    modes.CBC(
        bytearray(
            [119, 36, 86, 242, 167, 102, 76, 243, 57, 44, 53, 151, 233, 62, 87, 71]
        )
    ),
)

_PHONE_BY_REGION = {"AZ": "1", "AY": "86", "IN": "91", "EU": "44"}
_REGION_BY_COUNTRY = {"US": "AZ", "CA": "AZ", "MX": "AZ", "CN": "AY", "IN": "IN"}
_REGION_BY_PHONE = {"1": "AZ", "86": "AY", "91": "IN"}
_LOCAL_HOST_SCAN_MAX_RETRIES = 3

_LOGGER = logging.getLogger(__name__)


class EufyRoboVacCloudApiError(HomeAssistantError):
    """Raised when cloud onboarding calls fail."""


class EufyRoboVacCloudApiInvalidAuth(EufyRoboVacCloudApiError):
    """Raised when cloud onboarding credentials are invalid."""


@dataclass(slots=True, frozen=True)
class CloudDiscoveredRoboVac:
    """Normalized cloud-discovered RoboVac metadata."""

    device_id: str
    model: str
    name: str
    local_key: str
    host: str
    mac: str
    description: str
    protocol_version: str


def _unpadded_rsa(key_exponent: int, key_n: int, plaintext: bytes) -> bytes:
    """Perform RSA encryption without padding."""
    key_length = math.ceil(key_n.bit_length() / 8)
    input_nr = int.from_bytes(plaintext, byteorder="big")
    crypted_nr = pow(input_nr, key_exponent, key_n)
    return crypted_nr.to_bytes(key_length, byteorder="big")


def _shuffled_md5(value: str) -> str:
    """Shuffle MD5 hash in Tuya's expected order."""
    digest = md5(value.encode("utf-8")).hexdigest()
    return digest[8:16] + digest[0:8] + digest[24:32] + digest[16:24]


class _TuyaApiSession:
    """Minimal Tuya cloud session for looking up device local keys."""

    def __init__(self, *, username: str, region: str, timezone: str, phone_code: str) -> None:
        self._username = username
        self._phone_code = phone_code
        self._session_id: str | None = None
        self._base_url = _TUYA_BASE_URL.get(region, _TUYA_BASE_URL["EU"])
        self._session = requests.Session()
        self._session.headers.update(_TUYA_HEADERS)
        self._query_defaults = {
            "appVersion": "2.4.0",
            "deviceId": self._generate_device_id(),
            "platform": "sdk_gphone64_arm64",
            "clientId": "yx5v9uc3ef9wg3v9atje",
            "lang": "en",
            "osSystem": "12",
            "os": "Android",
            "timeZoneId": timezone,
            "ttid": "android",
            "et": "0.0.1",
            "sdkVersion": "3.0.8cAnker",
        }

    @staticmethod
    def _generate_device_id() -> str:
        expected_length = 44
        alphabet = string.ascii_letters + string.digits
        prefix = "8534c8ec0ed0"
        return prefix + "".join(
            random.choice(alphabet) for _ in range(expected_length - len(prefix))
        )

    @staticmethod
    def _sign(query_params: dict[str, str], encoded_post_data: str) -> str:
        signed_params = query_params.copy()
        if encoded_post_data:
            signed_params["postData"] = encoded_post_data
        pairs = sorted(signed_params.items())
        filtered_pairs = [pair for pair in pairs if pair[0] in _TUYA_SIGNATURE_FIELDS]
        message = "||".join(
            f"{key}={_shuffled_md5(value) if key == 'postData' else value}"
            for key, value in filtered_pairs
        )
        return hmac.HMAC(
            key=_TUYA_HMAC_KEY, msg=message.encode("utf-8"), digestmod=sha256
        ).hexdigest()

    def _request(
        self,
        *,
        action: str,
        version: str = "1.0",
        data: dict[str, Any] | None = None,
        requires_session: bool = True,
    ) -> dict[str, Any]:
        if requires_session and not self._session_id:
            self._acquire_session()

        query_params: dict[str, str] = {
            **self._query_defaults,
            "time": str(int(time.time())),
            "requestId": str(uuid.uuid4()),
            "a": action,
            "v": version,
        }
        encoded_post_data = json.dumps(data, separators=(",", ":")) if data else ""
        signed_query = {**query_params, "sign": self._sign(query_params, encoded_post_data)}

        try:
            response = self._session.post(
                f"{self._base_url}/api.json",
                params=signed_query,
                data={"postData": encoded_post_data} if encoded_post_data else None,
                timeout=10,
            )
            response.raise_for_status()
            response_json = response.json()
        except (requests.RequestException, ValueError) as err:
            raise EufyRoboVacCloudApiError(f"Tuya request failed ({action})") from err

        result = response_json.get("result")
        if not isinstance(result, dict):
            raise EufyRoboVacCloudApiError("Tuya response missing result payload")
        return result

    def _request_token(self) -> dict[str, Any]:
        return self._request(
            action="tuya.m.user.uid.token.create",
            data={"uid": self._username, "countryCode": self._phone_code},
            requires_session=False,
        )

    def _determine_password(self) -> str:
        padded_size = 16 * math.ceil(len(self._username) / 16)
        password_uid = self._username.zfill(padded_size)
        encryptor = _TUYA_PASSWORD_CIPHER.encryptor()
        encrypted_uid = encryptor.update(password_uid.encode("utf8")) + encryptor.finalize()
        return md5(encrypted_uid.hex().upper().encode("utf-8")).hexdigest()

    def _request_session(self, password: str) -> dict[str, Any]:
        token_response = self._request_token()
        encrypted_password = _unpadded_rsa(
            key_exponent=int(token_response["exponent"]),
            key_n=int(token_response["publicKey"]),
            plaintext=password.encode("utf-8"),
        )
        return self._request(
            action="tuya.m.user.uid.password.login.reg",
            data={
                "uid": self._username,
                "createGroup": True,
                "ifencrypt": 1,
                "passwd": encrypted_password.hex(),
                "countryCode": self._phone_code,
                "options": '{"group": 1}',
                "token": token_response["token"],
            },
            requires_session=False,
        )

    def _acquire_session(self) -> None:
        password = self._determine_password()
        session_response = self._request_session(password=password)
        self._session_id = session_response["sid"]
        self._query_defaults["sid"] = self._session_id
        if domain := session_response.get("domain", {}).get("mobileApiUrl"):
            self._base_url = domain
        if phone_code := session_response.get("phoneCode"):
            self._phone_code = phone_code
        elif region := session_response.get("domain", {}).get("regionCode"):
            self._phone_code = _PHONE_BY_REGION.get(region, _PHONE_BY_REGION["EU"])

    def get_device(self, dev_id: str) -> dict[str, Any]:
        """Fetch a Tuya device payload by device ID."""
        return self._request(action="tuya.m.device.get", data={"devId": dev_id})

    def close(self) -> None:
        """Close underlying HTTP session resources."""
        self._session.close()


class EufyRoboVacCloudApi:
    """Cloud API client for onboarding RoboVac devices."""

    def __init__(self, *, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def async_list_robovacs(self, hass: HomeAssistant) -> list[CloudDiscoveredRoboVac]:
        """Discover RoboVac devices from the account."""
        return await hass.async_add_executor_job(self._list_robovacs_sync)

    @staticmethod
    def _resolve_region_phone_timezone(
        *,
        user_info: dict[str, Any],
        settings: dict[str, Any],
    ) -> tuple[str, str, str]:
        if region := (
            settings.get("setting", {})
            .get("home_setting", {})
            .get("tuya_home", {})
            .get("tuya_region_code")
        ):
            resolved_region = str(region)
        elif phone_code := user_info.get("phone_code"):
            resolved_region = _REGION_BY_PHONE.get(str(phone_code), "EU")
        elif country_code := user_info.get("country"):
            resolved_region = _REGION_BY_COUNTRY.get(str(country_code), "EU")
        else:
            resolved_region = "EU"

        if phone_code := user_info.get("phone_code"):
            resolved_phone = str(phone_code)
        else:
            resolved_phone = _PHONE_BY_REGION.get(resolved_region, _PHONE_BY_REGION["EU"])

        timezone = str(user_info.get("timezone") or "UTC")
        return resolved_region, resolved_phone, timezone

    def _eufy_get(
        self,
        *,
        base_url: str,
        endpoint: str,
        user_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        headers = _EUFY_HEADERS.copy()
        headers["token"] = access_token
        headers["id"] = user_id
        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as err:
            raise EufyRoboVacCloudApiError(f"Eufy request failed ({endpoint})") from err
        if not isinstance(payload, dict):
            raise EufyRoboVacCloudApiError("Eufy response payload is invalid")
        return payload

    @staticmethod
    def _resolve_hosts_from_tinytuya_scan(
        missing_device_ids: set[str],
    ) -> dict[str, str]:
        """Resolve local hosts by scanning the LAN for Tuya broadcast packets."""
        if not missing_device_ids:
            return {}

        try:
            import tinytuya
        except ImportError:
            _LOGGER.debug("tinytuya unavailable for RoboVac host fallback")
            return {}

        try:
            scan_results = tinytuya.deviceScan(
                verbose=False,
                maxretry=_LOCAL_HOST_SCAN_MAX_RETRIES,
                color=False,
                poll=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("RoboVac host fallback scan failed", exc_info=True)
            return {}

        if not isinstance(scan_results, dict):
            return {}

        resolved_hosts: dict[str, str] = {}
        for ip_address, payload in scan_results.items():
            if not isinstance(ip_address, str) or not isinstance(payload, dict):
                continue
            device_id = str(payload.get("gwId") or payload.get("id") or "")
            if device_id in missing_device_ids:
                resolved_hosts[device_id] = ip_address

        return resolved_hosts

    def _apply_local_host_fallback(
        self, discovered_vacuums: list[CloudDiscoveredRoboVac]
    ) -> list[CloudDiscoveredRoboVac]:
        """Fill missing hosts from local Tuya discovery when cloud omits the IP."""
        missing_device_ids = {
            vacuum.device_id for vacuum in discovered_vacuums if not vacuum.host
        }
        if not missing_device_ids:
            return discovered_vacuums

        resolved_hosts = self._resolve_hosts_from_tinytuya_scan(missing_device_ids)
        if not resolved_hosts:
            return discovered_vacuums

        return [
            replace(
                vacuum,
                host=resolved_hosts.get(vacuum.device_id, vacuum.host),
            )
            for vacuum in discovered_vacuums
        ]

    def _list_robovacs_sync(self) -> list[CloudDiscoveredRoboVac]:
        login_payload = {
            **_EUFY_LOGIN_AUTH,
            "email": self._username,
            "password": self._password,
        }
        try:
            login_response = requests.post(
                _EUFY_LOGIN_URL,
                json=login_payload,
                headers=_EUFY_HEADERS,
                timeout=10,
            )
            login_response.raise_for_status()
            login_json = login_response.json()
        except (requests.RequestException, ValueError) as err:
            raise EufyRoboVacCloudApiError("Eufy login request failed") from err

        if login_json.get("res_code") != 1:
            raise EufyRoboVacCloudApiInvalidAuth("Invalid Eufy credentials")

        user_info = login_json.get("user_info")
        if not isinstance(user_info, dict):
            raise EufyRoboVacCloudApiError("Missing user info in Eufy login response")

        request_host = user_info.get("request_host")
        user_id = user_info.get("id")
        access_token = login_json.get("access_token")
        if not all([request_host, user_id, access_token]):
            raise EufyRoboVacCloudApiError("Eufy login response missing required fields")

        device_payload = self._eufy_get(
            base_url=str(request_host),
            endpoint="/v1/device/v2",
            user_id=str(user_id),
            access_token=str(access_token),
        )
        settings_payload = self._eufy_get(
            base_url=str(request_host),
            endpoint="/v1/user/setting",
            user_id=str(user_id),
            access_token=str(access_token),
        )

        region, phone_code, timezone = self._resolve_region_phone_timezone(
            user_info=user_info,
            settings=settings_payload,
        )
        tuya_session = _TuyaApiSession(
            username=f"eh-{user_id}",
            region=region,
            timezone=timezone,
            phone_code=phone_code,
        )

        vacuums: list[CloudDiscoveredRoboVac] = []
        try:
            for item in device_payload.get("devices", []):
                product = item.get("product", {})
                if product.get("appliance") != "Cleaning":
                    continue

                dev_id = str(item.get("id") or "")
                if not dev_id:
                    continue

                tuya_device = tuya_session.get_device(dev_id)
                local_key = str(tuya_device.get("localKey") or "")
                if not local_key:
                    continue

                wifi = item.get("wifi") or {}
                vacuums.append(
                    CloudDiscoveredRoboVac(
                        device_id=dev_id,
                        model=str(product.get("product_code") or ""),
                        name=str(item.get("alias_name") or item.get("name") or dev_id),
                        local_key=local_key,
                        host=str(wifi.get("ip") or ""),
                        mac=str(wifi.get("mac") or ""),
                        description=str(item.get("name") or ""),
                        protocol_version="3.3",
                    )
                )
        finally:
            tuya_session.close()

        return self._apply_local_host_fallback(vacuums)
