import datetime  # noqa: D100
import random

from .background_event_list import BackgroundEventList
from .key_event_list import KeyEventList
from .performance_test_results import PerformanceTestResults
from .sensor_data_encryptor import SensorDataEncryptor
from .sensor_data_util import feistel_cipher, timestamp_to_millis
from .system_info import SystemInfo
from .touch_event_list import TouchEventList

SDK_VERSION = "2.2.3"


class SensorDataBuilder:  # noqa: D101
    def __init__(self):  # noqa: D107
        self.sensor_collection_start_timestamp = datetime.datetime.now(datetime.UTC)
        self.device_info_time = random.randrange(3, 8) * 1000

        self.system_info = SystemInfo()
        self.system_info.randomize()

        self.touch_event_list = TouchEventList()
        self.key_event_list = KeyEventList()
        self.background_event_list = BackgroundEventList()

        self.performance_test_results = PerformanceTestResults()
        self.performance_test_results.randomize()

        self.sensor_data_encryptor = SensorDataEncryptor()

    def generate_sensor_data(self):  # noqa: D102
        self.touch_event_list.randomize(self.sensor_collection_start_timestamp)
        self.key_event_list.randomize(self.sensor_collection_start_timestamp)
        self.background_event_list.randomize(self.sensor_collection_start_timestamp)

        random_number = random.randrange(-(2**31), 2**31)

        orientation_event = self.generate_orientation_data_aa()
        orientation_event_count = orientation_event.count(";")
        motion_event = self.generate_motion_data_aa()
        motion_event_count = motion_event.count(";")

        sensor_data = ""
        sensor_data += SDK_VERSION
        sensor_data += "-1,2,-94,-100,"
        sensor_data += self.system_info.to_string()
        sensor_data += ","
        sensor_data += str(self.system_info.get_char_code_sum())
        sensor_data += ","
        sensor_data += str(random_number)
        sensor_data += ","
        sensor_data += str(
            int(timestamp_to_millis(self.sensor_collection_start_timestamp) / 2)
        )
        sensor_data += "-1,2,-94,-101,"
        sensor_data += "do_en"
        sensor_data += ","
        sensor_data += "dm_en"
        sensor_data += ","
        sensor_data += "t_en"
        sensor_data += "-1,2,-94,-102,"
        sensor_data += self.generate_edited_text()
        sensor_data += "-1,2,-94,-108,"
        sensor_data += self.key_event_list.to_string()
        sensor_data += "-1,2,-94,-117,"
        sensor_data += self.touch_event_list.to_string()
        sensor_data += "-1,2,-94,-111,"
        sensor_data += orientation_event
        sensor_data += "-1,2,-94,-109,"
        sensor_data += motion_event
        sensor_data += "-1,2,-94,-144,"
        sensor_data += self.generate_orientation_data_ac()
        sensor_data += "-1,2,-94,-142,"
        sensor_data += self.generate_orientation_data_ab()
        sensor_data += "-1,2,-94,-145,"
        sensor_data += self.generate_motion_data_ac()
        sensor_data += "-1,2,-94,-143,"
        sensor_data += self.generate_motion_event()
        sensor_data += "-1,2,-94,-115,"
        sensor_data += self.generate_misc_stat(
            orientation_event_count, motion_event_count
        )
        sensor_data += "-1,2,-94,-106,"
        sensor_data += self.generate_stored_values_f()
        sensor_data += ","
        sensor_data += self.generate_stored_values_g()
        sensor_data += "-1,2,-94,-120,"
        sensor_data += self.generate_stored_stack_traces()
        sensor_data += "-1,2,-94,-112,"
        sensor_data += self.performance_test_results.to_string()
        sensor_data += "-1,2,-94,-103,"
        sensor_data += self.background_event_list.to_string()

        encrypted_sensor_data = self.sensor_data_encryptor.encrypt_sensor_data(
            sensor_data
        )
        return encrypted_sensor_data

    def generate_edited_text(self):  # noqa: D102
        return ""

    def generate_orientation_data_aa(self):  # noqa: D102
        return ""

    def generate_motion_data_aa(self):  # noqa: D102
        return ""

    def generate_orientation_data_ac(self):  # noqa: D102
        return ""

    def generate_orientation_data_ab(self):  # noqa: D102
        return ""

    def generate_motion_data_ac(self):  # noqa: D102
        return ""

    def generate_motion_event(self):  # noqa: D102
        return ""

    def generate_misc_stat(  # noqa: D102
        self, orientation_data_count, motion_data_count
    ):  # noqa: D102
        sum_of_text_event_values = self.key_event_list.get_sum()
        sum_of_touch_event_timestamps_and_types = self.touch_event_list.get_sum()
        orientation_data_b = 0
        motion_data_b = 0
        overall_sum = (
            sum_of_text_event_values
            + sum_of_touch_event_timestamps_and_types
            + orientation_data_b
            + motion_data_b
        )

        now_timestamp = datetime.datetime.now(datetime.UTC)
        time_since_sensor_collection_start = int(
            (now_timestamp - self.sensor_collection_start_timestamp)
            / datetime.timedelta(milliseconds=1)
        )

        return ",".join(
            [
                str(sum_of_text_event_values),
                str(sum_of_touch_event_timestamps_and_types),
                str(orientation_data_b),
                str(motion_data_b),
                str(overall_sum),
                str(time_since_sensor_collection_start),
                str(len(self.key_event_list.key_events)),
                str(len(self.touch_event_list.touch_events)),
                str(orientation_data_count),
                str(motion_data_count),
                str(self.device_info_time),
                str(random.randrange(5, 15) * 1000),
                "0",
                str(
                    feistel_cipher(
                        overall_sum,
                        len(self.key_event_list.key_events)
                        + len(self.touch_event_list.touch_events)
                        + orientation_data_count
                        + motion_data_count,
                        time_since_sensor_collection_start,
                    )
                ),
                str(timestamp_to_millis(self.sensor_collection_start_timestamp)),
                "0",
            ]
        )

    def generate_stored_values_f(self):  # noqa: D102
        return "-1"

    def generate_stored_values_g(self):  # noqa: D102
        return "0"

    def generate_stored_stack_traces(self):  # noqa: D102
        return ""
