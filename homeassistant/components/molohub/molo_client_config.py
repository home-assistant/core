"""Configuration class for Molohub."""


class MoloConfigs:
    """Configuration class for Molohub."""

    config_object = dict()

    config_debug = {
        'server': {
            'haweb': "127.0.0.1",
            'host': "127.0.0.1",
            'port': 4443,
            'bufsize': 1024
        },
        'ha': {
            'host': "127.0.0.1",
            'port': 8123
        }
    }

    config_release = {
        'server': {
            'haweb': "www.molo.cn",
            'host': "haprx.molo.cn",
            'port': 4443,
            'bufsize': 1024
        },
        'ha': {
            'host': "127.0.0.1",
            'port': 8123
        }
    }

    def load(self, mode):
        """Load configs by reading mode in configuration.yaml."""
        if mode == 'debug':
            self.config_object = self.config_debug
        else:
            self.config_object = self.config_release


MOLO_CONFIGS = MoloConfigs()
