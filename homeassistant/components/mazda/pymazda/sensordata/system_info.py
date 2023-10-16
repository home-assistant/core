import random  # noqa: D100
import secrets

from .android_builds import AndroidBuilds
from .sensor_data_util import percent_encode, sum_char_codes

SCREEN_SIZES = [[1280, 720], [1920, 1080], [2560, 1440]]

ANDROID_VERSION_TO_SDK_VERSION = {
    "11": 30,
    "10": 29,
    "9": 28,
    "8.1.0": 27,
    "8.0.0": 26,
    "7.1": 25,
    "7.0": 24,
}


class SystemInfo:  # noqa: D101
    def __init__(self):  # noqa: D107
        self.android_builds = AndroidBuilds()

    def randomize(self):  # noqa: D102
        device_model, device = random.choice(
            list(self.android_builds.get_builds().items())
        )
        codename = device["codename"]
        build = random.choice(device["builds"])
        build_version_incremental = random.randrange(1000000, 9999999)

        self.screen_height, self.screen_width = random.choice(SCREEN_SIZES)
        self.battery_charging = random.randrange(0, 10) <= 1
        self.battery_level = random.randrange(10, 90)
        self.orientation = 1
        self.language = "en"
        self.android_version = build["version"]
        self.rotation_lock = "1" if random.randrange(0, 10) > 1 else "0"
        self.build_model = device_model
        self.build_bootloader = str(random.randrange(1000000, 9999999))
        self.build_hardware = codename
        self.package_name = "com.interrait.mymazda"
        self.android_id = secrets.token_bytes(8).hex()
        self.keyboard = 0
        self.adb_enabled = False
        self.build_version_codename = "REL"
        self.build_version_incremental = build_version_incremental
        self.build_version_sdk = ANDROID_VERSION_TO_SDK_VERSION.get(build["version"])
        self.build_manufacturer = "Google"
        self.build_product = codename
        self.build_tags = "release-keys"
        self.build_type = "user"
        self.build_user = "android-build"
        self.build_display = build["buildId"]
        self.build_board = codename
        self.build_brand = "google"
        self.build_device = codename
        self.build_fingerprint = f"google/{codename}/{codename}:{build['version']}/{build['buildId']}/{build_version_incremental}:user/release-keys"
        self.build_host = f"abfarm-{random.randrange(10000, 99999)}"
        self.build_id = build["buildId"]

    def to_string(self):  # noqa: D102
        return ",".join(
            [
                "-1",
                "uaend",
                "-1",
                str(self.screen_height),
                str(self.screen_width),
                ("1" if self.battery_charging else "0"),
                str(self.battery_level),
                str(self.orientation),
                percent_encode(self.language),
                percent_encode(self.android_version),
                self.rotation_lock,
                percent_encode(self.build_model),
                percent_encode(self.build_bootloader),
                percent_encode(self.build_hardware),
                "-1",
                self.package_name,
                "-1",
                "-1",
                self.android_id,
                "-1",
                str(self.keyboard),
                "1" if self.adb_enabled else "0",
                percent_encode(self.build_version_codename),
                percent_encode(str(self.build_version_incremental)),
                str(self.build_version_sdk),
                percent_encode(self.build_manufacturer),
                percent_encode(self.build_product),
                percent_encode(self.build_tags),
                percent_encode(self.build_type),
                percent_encode(self.build_user),
                percent_encode(self.build_display),
                percent_encode(self.build_board),
                percent_encode(self.build_brand),
                percent_encode(self.build_device),
                percent_encode(self.build_fingerprint),
                percent_encode(self.build_host),
                percent_encode(self.build_id),
            ]
        )

    def get_char_code_sum(self):  # noqa: D102
        return sum_char_codes(self.to_string())
