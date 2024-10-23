# mypy: ignore-errors
import sys
import six

from ..utils import underscore_to_camelcase


class AccountService(object):
    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._service_root = service_root
        self._devices = []

        self._acc_endpoint = '%s/setup/web/device' % self._service_root
        self._account_devices_url = '%s/getDevices' % self._acc_endpoint

        req = self.session.get(self._account_devices_url, params=self.params)
        self.response = req.json()

        for device_info in self.response['devices']:
            # device_id = device_info['udid']
            # self._devices[device_id] = AccountDevice(device_info)
            self._devices.append(AccountDevice(device_info))

    @property
    def devices(self):
        return self._devices


@six.python_2_unicode_compatible
class AccountDevice(dict): # type: ignore[type-arg]
    def __init__(self, device_info):
        super(AccountDevice, self).__init__(device_info)

    def __getattr__(self, name):
        try:
            return self[underscore_to_camelcase(name)]
        except KeyError:
            raise AttributeError(name)

    def __str__(self):
        return u"{display_name}: {name}".format(
            display_name=self.model_display_name,
            name=self.name,
        )

    def __repr__(self):
        return '<{display}>'.format(
            display=(
                six.text_type(self)
                if sys.version_info[0] >= 3 else
                six.text_type(self).encode('utf8', 'replace')
            )
        )
