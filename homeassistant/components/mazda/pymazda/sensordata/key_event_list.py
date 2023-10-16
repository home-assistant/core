import datetime  # noqa: D100
import random


class KeyEvent:  # noqa: D101
    def __init__(self, time, id_char_code_sum, longer_than_before):  # noqa: D107
        self.time = time
        self.id_char_code_sum = id_char_code_sum
        self.longer_than_before = longer_than_before

    def to_string(self):  # noqa: D102
        return f"2,{self.time},{self.id_char_code_sum}{',1' if self.longer_than_before else ''};"


class KeyEventList:  # noqa: D101
    def __init__(self):  # noqa: D107
        self.key_events = []

    def randomize(self, sensor_collection_start_timestamp):  # noqa: D102
        self.key_events = []

        if random.randrange(0, 20) > 0:
            return

        now_timestamp = datetime.datetime.now(datetime.UTC)
        time_since_sensor_collection_start = int(
            (now_timestamp - sensor_collection_start_timestamp)
            / datetime.timedelta(milliseconds=1)
        )

        if time_since_sensor_collection_start < 10000:
            return

        event_count = random.randrange(2, 5)
        id_char_code_sum = random.randrange(517, 519)
        for i in range(event_count):
            time = random.randrange(5000, 8000) if i == 0 else random.randrange(10, 50)
            self.key_events.append(
                KeyEvent(time, id_char_code_sum, random.randrange(0, 2) == 0)
            )

    def to_string(self):  # noqa: D102
        return "".join(event.to_string() for event in self.key_events)

    def get_sum(self):  # noqa: D102
        sum = 0
        for key_event in self.key_events:
            sum += key_event.id_char_code_sum
            sum += key_event.time
            sum += 2
        return sum
