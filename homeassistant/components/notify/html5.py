"""
HTML5 Push Messaging notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.html5/
"""
import base64
import datetime
import hashlib
import json
import logging
import os
import time
import uuid
import ecdsa

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR,
                                 HTTP_UNAUTHORIZED, URL_ROOT)
from homeassistant.util import ensure_unique_string
from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA,
    BaseNotificationService, PLATFORM_SCHEMA)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.frontend import add_manifest_json_key
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['https://github.com/web-push-libs/pywebpush/archive/'
                '65954b119153868b3a74b1ffdb83159213f8a4c6.zip#'
                'pywebpush==0.6.1', 'PyJWT==1.4.2']

DEPENDENCIES = ['frontend']

_LOGGER = logging.getLogger(__name__)

REGISTRATIONS_FILE = 'html5_push_registrations.conf'
KEYS_FILE = 'html5_push_key.pem'
VAPID_EMAIL = 'mailto:webpush@home-assistant.io'

ATTR_GCM_SENDER_ID = 'gcm_sender_id'
ATTR_GCM_API_KEY = 'gcm_api_key'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(ATTR_GCM_SENDER_ID): cv.string,
    vol.Optional(ATTR_GCM_API_KEY): cv.string,
})

ATTR_SUBSCRIPTION = 'subscription'
ATTR_BROWSER = 'browser'

ATTR_ENDPOINT = 'endpoint'
ATTR_KEYS = 'keys'
ATTR_AUTH = 'auth'
ATTR_P256DH = 'p256dh'

ATTR_TAG = 'tag'
ATTR_ACTION = 'action'
ATTR_ACTIONS = 'actions'
ATTR_TYPE = 'type'
ATTR_URL = 'url'

ATTR_JWT = 'jwt'

# The number of days after the moment a notification is sent that a JWT
# is valid.
JWT_VALID_DAYS = 7

KEYS_SCHEMA = vol.All(dict,
                      vol.Schema({
                          vol.Required(ATTR_AUTH): cv.string,
                          vol.Required(ATTR_P256DH): cv.string
                          }))

SUBSCRIPTION_SCHEMA = vol.All(dict,
                              vol.Schema({
                                  # pylint: disable=no-value-for-parameter
                                  vol.Required(ATTR_ENDPOINT): vol.Url(),
                                  vol.Required(ATTR_KEYS): KEYS_SCHEMA
                                  }))

REGISTER_SCHEMA = vol.Schema({
    vol.Required(ATTR_SUBSCRIPTION): SUBSCRIPTION_SCHEMA,
    vol.Required(ATTR_BROWSER): vol.In(['chrome', 'firefox'])
})

CALLBACK_EVENT_PAYLOAD_SCHEMA = vol.Schema({
    vol.Required(ATTR_TAG): cv.string,
    vol.Required(ATTR_TYPE): vol.In(['received', 'clicked', 'closed']),
    vol.Required(ATTR_TARGET): cv.string,
    vol.Optional(ATTR_ACTION): cv.string,
    vol.Optional(ATTR_DATA): dict,
})

NOTIFY_CALLBACK_EVENT = 'html5_notification'

# badge and timestamp are Chrome specific (not in official spec)

HTML5_SHOWNOTIFICATION_PARAMETERS = ('actions', 'badge', 'body', 'dir',
                                     'icon', 'lang', 'renotify',
                                     'requireInteraction', 'tag', 'timestamp',
                                     'vibrate')


class VapidException(Exception):
    """An exception wrapper for Vapid."""
    pass


class Vapid(object):
    """Minimal VAPID signature generation library. """
    _private_key = None
    _public_key = None
    _hasher = hashlib.sha256

    def __init__(self, private_key_file=None, private_key=None):
        """Initialize VAPID using an optional file containing a private key
        in PEM format.
        :param private_key_file: The name of the file containing the
        private key
        """
        if private_key_file:
            if not os.path.isfile(private_key_file):
                self.save_key(private_key_file)
                return
            private_key = open(private_key_file, 'r').read()
        if private_key:
            try:
                if "BEGIN EC" in private_key:
                    self._private_key = ecdsa.SigningKey.from_pem(private_key)
                else:
                    self._private_key = \
                        ecdsa.SigningKey.from_der(
                            base64.urlsafe_b64decode(private_key))
            except Exception as exc:
                logging.error("Could not open private key file: %s", repr(exc))
                raise VapidException(exc)
            self._public_key = self._private_key.get_verifying_key()

    @property
    def private_key(self):
        """Return the private key."""
        if not self._private_key:
            raise VapidException(
                "No private key defined. Please import or generate a key.")
        return self._private_key

    @private_key.setter
    def private_key(self, value):
        """Set the private key."""
        self._private_key = value

    @property
    def public_key(self):
        """Return the public key."""
        if not self._public_key:
            self._public_key = self.private_key.get_verifying_key()
        return self._public_key

    @property
    def private_key_base64(self):
        """Return the base64'ed private key."""
        return base64.urlsafe_b64encode(self.private_key.to_string())

    @property
    def public_key_base64(self):
        """Return the base64'ed public key."""
        return base64.urlsafe_b64encode(self.public_key.to_string())

    def generate_keys(self):
        """Generate a valid ECDSA Key Pair."""
        self.private_key = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
        self.public_key

    def save_key(self, key_file):
        """Save the private key to a PEM file."""
        file = open(key_file, "wb")
        if not self._private_key:
            self.generate_keys()
        file.write(self._private_key.to_pem())
        file.close()

    def save_public_key(self, key_file):
        """Save the public key to a PEM file.
        :param key_file: The name of the file to save the public key
        """
        with open(key_file, "wb") as file:
            file.write(self.public_key.to_pem())
            file.close()

    def validate(self, token):
        """Sign a Valdiation token from the dashboard"""
        sig = self.private_key.sign(token, hashfunc=self._hasher)
        token = base64.urlsafe_b64encode(sig)
        return token

    def verify_token(self, sig, token):
        """Verify the signature against the token."""
        hsig = base64.urlsafe_b64decode(sig)
        return self.public_key.verify(hsig, token,
                                      hashfunc=self._hasher)

    def sign(self, claims, crypto_key=None):
        """Sign a set of claims.
        :param claims: JSON object containing the JWT claims to use.
        :param crypto_key: Optional existing crypto_key header content. The
            vapid public key will be appended to this data.
        :returns result: a hash containing the header fields to use in
            the subscription update.
        """
        from jose import jws
        if not claims.get('exp'):
            claims['exp'] = int(time.time()) + 86400
        if not claims.get('sub'):
            raise VapidException(
                "Missing 'sub' from claims. "
                "'sub' is your admin email as a mailto: link.")
        sig = jws.sign(claims, self.private_key, algorithm="ES256")
        pkey = 'p256ecdsa='
        pkey += base64.urlsafe_b64encode(self.public_key.to_string())
        if crypto_key:
            crypto_key = crypto_key + ',' + pkey
        else:
            crypto_key = pkey

        return {"Authorization": "Bearer " + sig.strip('='),
                "Crypto-Key": crypto_key}


def get_service(hass, config):
    """Get the HTML5 push notification service."""
    reg_json_path = hass.config.path(REGISTRATIONS_FILE)
    keys_path = hass.config.path(KEYS_FILE)

    registrations = _load_config(reg_json_path)

    if registrations is None:
        return None

    print("Path", keys_path)

    vapid = Vapid(private_key_file=keys_path)

    print("Keys input", vapid)

    hass.wsgi.register_view(
        HTML5PushRegistrationView(hass, registrations, reg_json_path))
    hass.wsgi.register_view(HTML5PushCallbackView(hass, registrations))
    hass.wsgi.register_view(HTML5PushKeysView(hass, vapid))

    gcm_api_key = config.get(ATTR_GCM_API_KEY)
    gcm_sender_id = config.get(ATTR_GCM_SENDER_ID)

    if gcm_sender_id is not None:
        add_manifest_json_key(ATTR_GCM_SENDER_ID,
                              config.get(ATTR_GCM_SENDER_ID))

    return HTML5NotificationService(gcm_api_key, registrations,
                                    reg_json_path, vapid)


def _load_config(filename):
    """Load configuration."""
    if not os.path.isfile(filename):
        return {}

    try:
        with open(filename, 'r') as fdesc:
            inp = fdesc.read()

        # In case empty file
        if not inp:
            return {}

        return json.loads(inp)
    except (IOError, ValueError) as error:
        _LOGGER.error('Reading config file %s failed: %s', filename, error)
        return None


def _save_config(filename, config):
    """Save configuration."""
    try:
        with open(filename, 'w') as fdesc:
            fdesc.write(json.dumps(config))
    except (IOError, TypeError) as error:
        _LOGGER.error('Saving config file failed: %s', error)
        return False
    return True


class HTML5PushRegistrationView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    url = '/api/notify.html5'
    name = 'api:notify.html5'

    def __init__(self, hass, registrations, json_path):
        """Init HTML5PushRegistrationView."""
        super().__init__(hass)
        self.registrations = registrations
        self.json_path = json_path

    def post(self, request):
        """Accept the POST request for push registrations from a browser."""
        try:
            data = REGISTER_SCHEMA(request.json)
        except vol.Invalid as ex:
            return self.json_message(humanize_error(request.json, ex),
                                     HTTP_BAD_REQUEST)

        name = ensure_unique_string('unnamed device',
                                    self.registrations.keys())

        self.registrations[name] = data

        if not _save_config(self.json_path, self.registrations):
            return self.json_message('Error saving registration.',
                                     HTTP_INTERNAL_SERVER_ERROR)

        return self.json_message('Push notification subscriber registered.')

    def delete(self, request):
        """Delete a registration."""
        subscription = request.json.get(ATTR_SUBSCRIPTION)

        found = None

        for key, registration in self.registrations.items():
            if registration.get(ATTR_SUBSCRIPTION) == subscription:
                found = key
                break

        if not found:
            # If not found, unregistering was already done. Return 200
            return self.json_message('Registration not found.')

        reg = self.registrations.pop(found)

        if not _save_config(self.json_path, self.registrations):
            self.registrations[found] = reg
            return self.json_message('Error saving registration.',
                                     HTTP_INTERNAL_SERVER_ERROR)

        return self.json_message('Push notification subscriber unregistered.')


class HTML5PushCallbackView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    requires_auth = False
    url = '/api/notify.html5/callback'
    name = 'api:notify.html5/callback'

    def __init__(self, hass, registrations):
        """Init HTML5PushCallbackView."""
        super().__init__(hass)
        self.registrations = registrations

    def decode_jwt(self, token):
        """Find the registration that signed this JWT and return it."""
        import jwt

        # 1.  Check claims w/o verifying to see if a target is in there.
        # 2.  If target in claims, attempt to verify against the given name.
        # 2a. If decode is successful, return the payload.
        # 2b. If decode is unsuccessful, return a 401.

        target_check = jwt.decode(token, verify=False)
        if target_check[ATTR_TARGET] in self.registrations:
            possible_target = self.registrations[target_check[ATTR_TARGET]]
            key = possible_target[ATTR_SUBSCRIPTION][ATTR_KEYS][ATTR_AUTH]
            try:
                return jwt.decode(token, key)
            except jwt.exceptions.DecodeError:
                pass

        return self.json_message('No target found in JWT',
                                 status_code=HTTP_UNAUTHORIZED)

    # The following is based on code from Auth0
    # https://auth0.com/docs/quickstart/backend/python
    # pylint: disable=too-many-return-statements
    def check_authorization_header(self, request):
        """Check the authorization header."""
        import jwt
        auth = request.headers.get('Authorization', None)
        if not auth:
            return self.json_message('Authorization header is expected',
                                     status_code=HTTP_UNAUTHORIZED)

        parts = auth.split()

        if parts[0].lower() != 'bearer':
            return self.json_message('Authorization header must '
                                     'start with Bearer',
                                     status_code=HTTP_UNAUTHORIZED)
        elif len(parts) != 2:
            return self.json_message('Authorization header must '
                                     'be Bearer token',
                                     status_code=HTTP_UNAUTHORIZED)

        token = parts[1]
        try:
            payload = self.decode_jwt(token)
        except jwt.exceptions.InvalidTokenError:
            return self.json_message('token is invalid',
                                     status_code=HTTP_UNAUTHORIZED)
        return payload

    def post(self, request):
        """Accept the POST request for push registrations event callback."""
        auth_check = self.check_authorization_header(request)
        if not isinstance(auth_check, dict):
            return auth_check

        event_payload = {
            ATTR_TAG: request.json.get(ATTR_TAG),
            ATTR_TYPE: request.json[ATTR_TYPE],
            ATTR_TARGET: auth_check[ATTR_TARGET],
        }

        if request.json.get(ATTR_ACTION) is not None:
            event_payload[ATTR_ACTION] = request.json.get(ATTR_ACTION)

        if request.json.get(ATTR_DATA) is not None:
            event_payload[ATTR_DATA] = request.json.get(ATTR_DATA)

        try:
            event_payload = CALLBACK_EVENT_PAYLOAD_SCHEMA(event_payload)
        except vol.Invalid as ex:
            _LOGGER.warning('Callback event payload is not valid! %s',
                            humanize_error(event_payload, ex))

        event_name = '{}.{}'.format(NOTIFY_CALLBACK_EVENT,
                                    event_payload[ATTR_TYPE])
        self.hass.bus.fire(event_name, event_payload)
        return self.json({'status': 'ok',
                          'event': event_payload[ATTR_TYPE]})


class HTML5PushKeysView(HomeAssistantView):
    """Provides the VAPID keys to the browser."""

    url = '/api/notify.html5/vapid'
    name = 'api:notify.html5:vapid'

    def __init__(self, hass, vapid):
        """Init HTML5PushKeysView."""
        super().__init__(hass)
        self.vapid = vapid

    def get(self, request):
        """Return VAPID keys to browser."""
        return self.Response(self.vapid.public_key_base64,
                             mimetype="text/plain", status=200)


# pylint: disable=too-few-public-methods
class HTML5NotificationService(BaseNotificationService):
    """Implement the notification service for HTML5."""

    # pylint: disable=too-many-arguments
    def __init__(self, gcm_key, registrations, json_path, vapid):
        """Initialize the service."""
        self._gcm_key = gcm_key
        self.registrations = registrations
        self.json_path = json_path
        self.vapid = vapid

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        targets = {}
        for registration in self.registrations:
            targets[registration] = registration
        return targets

    # pylint: disable=too-many-locals, too-many-branches
    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        import jwt
        from pywebpush import WebPusher

        timestamp = int(time.time())
        tag = str(uuid.uuid4())

        payload = {
            'badge': '/static/images/notification-badge.png',
            'body': message,
            ATTR_DATA: {},
            'icon': '/static/icons/favicon-192x192.png',
            ATTR_TAG: tag,
            'timestamp': (timestamp*1000),  # Javascript ms since epoch
            ATTR_TITLE: kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        }

        data = kwargs.get(ATTR_DATA)

        if data:
            # Pick out fields that should go into the notification directly vs
            # into the notification data dictionary.

            for key, val in data.copy().items():
                if key in HTML5_SHOWNOTIFICATION_PARAMETERS:
                    payload[key] = val
                    del data[key]

            payload[ATTR_DATA] = data

        if (payload[ATTR_DATA].get(ATTR_URL) is None and
                payload.get(ATTR_ACTIONS) is None):
            payload[ATTR_DATA][ATTR_URL] = URL_ROOT

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = self.registrations.keys()
        elif not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            info = self.registrations.get(target)
            if info is None:
                _LOGGER.error('%s is not a valid HTML5 push notification'
                              ' target!', target)
                continue

            found_sub = info[ATTR_SUBSCRIPTION]

            jwt_exp = (datetime.datetime.fromtimestamp(timestamp) +
                       datetime.timedelta(days=JWT_VALID_DAYS))
            jwt_secret = found_sub[ATTR_KEYS][ATTR_AUTH]
            jwt_claims = {'exp': jwt_exp, 'nbf': timestamp,
                          'iat': timestamp, ATTR_TARGET: target,
                          ATTR_TAG: payload[ATTR_TAG]}
            jwt_token = jwt.encode(jwt_claims, jwt_secret).decode('utf-8')
            payload[ATTR_DATA][ATTR_JWT] = jwt_token

            headers = {}

            if "https://fcm.googleapis.com/" in found_sub.ATTR_ENDPOINT:
                headers = self.vapid.sign({"aud": "https://fcm.googleapis.com",
                                           "sub": VAPID_EMAIL})

            # Send the notification
            resp = WebPusher(found_sub).send(
                json.dumps(payload), headers=headers,
                gcm_key=self._gcm_key, ttl='86400')

            if resp.status_code == 410:
                found = None

                for key, registration in self.registrations.items():
                    if registration.get(ATTR_SUBSCRIPTION) == found_sub:
                        found = key
                        break

                if not found:
                    # If not found, unregistering was already done. Return 200
                    _LOGGER.error(("Unable to delete registration because",
                                   "it was not found in the file."))
                    return

                reg = self.registrations.pop(found)

                if not _save_config(self.json_path, self.registrations):
                    self.registrations[found] = reg
                    _LOGGER.error('Error saving registrations file.')

                _LOGGER.info(('Push service notified us that the target',
                              '(%s) was unregistered so it has been',
                              'removed from the registrations file.'),
                             found_sub)
                return
