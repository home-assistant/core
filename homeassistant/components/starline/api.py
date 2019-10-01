import hashlib
import requests

from .device import StarlineDevice
from .const import LOGGER


class StarlineAuth():
    def __init__(self):
        self._session = requests.Session()

    # TODO: async all methods
    def get_app_code(self, app_id, app_secret):
        """
        Получение кода приложения для дальнейшего получения токена.
        Идентификатор приложения и пароль выдаются контактным лицом СтарЛайн.
        :param app_id: Идентификатор приложения
        :param app_secret: Пароль приложения
        :return: Код, необходимый для получения токена приложения
        """
        url = 'https://id.starline.ru/apiV3/application/getCode/'
        LOGGER.debug('execute request: {}'.format(url))

        payload = {
            'appId': app_id,
            'secret': hashlib.md5(app_secret.encode('utf-8')).hexdigest()
        }

        r = self._session.get(url, params=payload)
        r.encoding = 'utf-8'
        response = r.json()
        LOGGER.debug('payload : {}'.format(payload))
        LOGGER.debug('response info: {}'.format(r))
        LOGGER.debug('response data: {}'.format(response))
        if int(response['state']) == 1:
            app_code = response['desc']['code']
            LOGGER.debug('Application code: {}'.format(app_code))
            return app_code
        raise Exception(response)

    def get_app_token(self, app_id, app_secret, app_code):
        """
        Получение токена приложения для дальнейшей авторизации.
        Время жизни токена приложения - 4 часа.
        Идентификатор приложения и пароль можно получить на my.starline.ru.
        :param app_id: Идентификатор приложения
        :param app_secret: Пароль приложения
        :param app_code: Код приложения
        :return: Токен приложения
        """
        url = 'https://id.starline.ru/apiV3/application/getToken/'
        LOGGER.debug('execute request: {}'.format(url))
        payload = {
            'appId': app_id,
            'secret': hashlib.md5((app_secret + app_code).encode('utf-8')).hexdigest()
        }
        r = self._session.get(url, params=payload)
        r.encoding = 'utf-8'
        response = r.json()
        LOGGER.debug('payload: {}'.format(payload))
        LOGGER.debug('response info: {}'.format(r))
        LOGGER.debug('response data: {}'.format(response))
        if int(response['state']) == 1:
            app_token = response['desc']['token']
            LOGGER.debug('Application token: {}'.format(app_token))
            return app_token
        raise Exception(response)

    def get_slid_user_token(self, app_token, user_login, user_password, sms_code=None, captcha_sid=None, captcha_code=None):
        """
        Аутентификация пользователя по логину и паролю.
        Неверные данные авторизации или слишком частое выполнение запроса авторизации с одного
        ip-адреса может привести к запросу капчи.
        Для того, чтобы сервер SLID корректно обрабатывал клиентский IP,
        необходимо проксировать его в параметре user_ip.
        В противном случае все запросы авторизации будут фиксироваться для IP-адреса сервера приложения, что приведет к частому требованию капчи.
        :param sid_url: URL StarLineID сервера
        :param app_token: Токен приложения
        :param user_login: Логин пользователя
        :param user_password: Пароль пользователя
        :return: Токен, необходимый для работы с данными пользователя. Данный токен потребуется для авторизации на StarLine API сервере.
        """
        url = 'https://id.starline.ru/apiV3/user/login/'
        LOGGER.debug('execute request: {}'.format(url))
        payload = {
            'token': app_token
        }
        data = {}
        data["login"] = user_login
        data["pass"] = hashlib.sha1(user_password.encode('utf-8')).hexdigest()
        if sms_code is not None:
            data["smsCode"] = sms_code
        if (captcha_sid is not None) and (captcha_code is not None):
            data["captchaSid"] = captcha_sid
            data["captchaCode"] = captcha_code

        r = self._session.post(url, params=payload, data=data)
        r.encoding = 'utf-8'
        response = r.json()
        LOGGER.debug('payload : {}'.format(payload))
        LOGGER.debug('data : {}'.format(data))
        LOGGER.debug('response info: {}'.format(r))
        LOGGER.debug('response data: {}'.format(response))
        state = int(response['state'])
        if (state == 1) or (state == 2) or (state == 0 and 'captchaSid' in response['desc']) or (state == 0 and 'phone' in response['desc']):
            return state == 1, response['desc']
        LOGGER.debug('response exception: {}'.format(response))
        raise Exception(response)

    def get_user_id(self, slid_token):
        """
        Авторизация пользователя по токену StarLineID. Токен авторизации предварительно необходимо получить на сервере StarLineID.
        :param slid_token: Токен StarLineID
        :return: Токен пользователя на StarLineAPI
        """
        url = 'https://developer.starline.ru/json/v2/auth.slid'
        LOGGER.debug('execute request: {}'.format(url))
        data = {
            'slid_token': slid_token
        }
        r = self._session.post(url, json=data)
        r.encoding = 'utf-8'
        response = r.json()
        LOGGER.debug('response info: {}'.format(r))
        LOGGER.debug('response data: {}'.format(response))
        slnet_token = r.cookies["slnet"]
        LOGGER.debug('slnet token: {}'.format(slnet_token))
        return slnet_token, response['user_id']


class StarlineApi():
    def __init__(self, user_id, slnet_token):
        self._session = requests.Session()
        self._user_id = user_id
        self._slnet_token = slnet_token
        self._devices = {}
        self._update_listeners = []

    def update(self, now=None):
        devices = self.get_user_info()

        for device_data in devices:
            device_id = device_data["device_id"]
            if device_id not in self._devices:
                self._devices[device_id] = StarlineDevice()
            self._devices[device_id].update(device_data)

        for listener in self._update_listeners:
            listener()

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)

    @property
    def devices(self):
        return self._devices

    # TODO: async all methods
    def get_user_info(self):
        url = "https://developer.starline.ru/json/v2/user/{}/user_info".format(self._user_id)
        LOGGER.debug('execute request: {}'.format(url))

        r = self._session.get(url, headers={"Cookie": "slnet=" + self._slnet_token})
        r.encoding = 'utf-8'
        response = r.json()
        LOGGER.debug('response info: {}'.format(r))
        LOGGER.debug('response data: {}'.format(response))
        code = int(response['code'])
        if code == 200:
            return response['devices'] + response['shared_devices']
        return None