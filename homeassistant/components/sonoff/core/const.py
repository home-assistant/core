DOMAIN = "sonoff"

CONF_APPID = "appid"
CONF_APPSECRET = "appsecret"
CONF_DEBUG = "debug"
CONF_DEFAULT_CLASS = "default_class"
CONF_DEVICEKEY = "devicekey"
CONF_RFBRIDGE = "rfbridge"

CONF_MODES = ["auto", "cloud", "local"]

PRIVATE_KEYS = (
    'bindInfos', 'bssid', 'mac', 'p2pinfo', 'ssid', 'staMac', 'timers',
)


def source_hash() -> str:
    if source_hash.__doc__:
        return source_hash.__doc__

    try:
        import hashlib
        import os

        m = hashlib.md5()
        path = os.path.dirname(os.path.dirname(__file__))
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                path = os.path.join(root, file)
                with open(path, "rb") as f:
                    m.update(f.read())

        source_hash.__doc__ = m.hexdigest()[:7]
        return source_hash.__doc__

    except Exception as e:
        return f"{type(e).__name__}: {e}"
