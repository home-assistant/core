import datetime  # noqa: D100
import random


class TouchEvent:  # noqa: D101
    def __init__(self, type, time, pointer_count, tool_type):  # noqa: D107
        self.type = type
        self.time = time
        self.pointer_count = pointer_count
        self.tool_type = tool_type

    def to_string(self):  # noqa: D102
        return (
            f"{self.type},{self.time},0,0,{self.pointer_count},1,{self.tool_type},-1;"
        )


class TouchEventList:  # noqa: D101
    def __init__(self):  # noqa: D107
        self.touch_events = []

    def randomize(self, sensor_collection_start_timestamp):  # noqa: D102
        self.touch_events = []

        now_timestamp = datetime.datetime.now(datetime.UTC)
        time_since_sensor_collection_start = int(
            (now_timestamp - sensor_collection_start_timestamp)
            / datetime.timedelta(milliseconds=1)
        )

        if time_since_sensor_collection_start < 3000:
            return
        elif (
            time_since_sensor_collection_start >= 3000
            and time_since_sensor_collection_start < 5000
        ):
            # down event
            self.touch_events.append(
                TouchEvent(
                    2,
                    time_since_sensor_collection_start - random.randrange(1000, 2000),
                    1,
                    1,
                )
            )

            # move events
            num_move_events = random.randrange(2, 9)
            for i in range(num_move_events):  # noqa: B007
                self.touch_events.append(TouchEvent(1, random.randrange(3, 50), 1, 1))

            # up event
            self.touch_events.append(TouchEvent(3, random.randrange(3, 100), 1, 1))
        elif (
            time_since_sensor_collection_start >= 5000
            and time_since_sensor_collection_start < 10000
        ):
            for i in range(2):
                # down event
                self.touch_events.append(
                    TouchEvent(
                        2, random.randrange(100, 1000) + (5000 if i == 1 else 0), 1, 1
                    )
                )

                # move events
                num_move_events = random.randrange(2, 9)
                for i in range(num_move_events):  # noqa: B007
                    self.touch_events.append(
                        TouchEvent(1, random.randrange(3, 50), 1, 1)
                    )

                # up event
                self.touch_events.append(TouchEvent(3, random.randrange(3, 100), 1, 1))
        else:
            for i in range(3):
                timestamp_offset = 0
                if i == 0:
                    timestamp_offset = time_since_sensor_collection_start - 9000
                else:
                    timestamp_offset = random.randrange(2000, 3000)

                # down event
                self.touch_events.append(
                    TouchEvent(2, random.randrange(100, 1000) + timestamp_offset, 1, 1)
                )

                # move events
                num_move_events = random.randrange(2, 9)
                for i in range(num_move_events):  # noqa: B007
                    self.touch_events.append(
                        TouchEvent(1, random.randrange(3, 50), 1, 1)
                    )

                # up event
                self.touch_events.append(TouchEvent(3, random.randrange(3, 100), 1, 1))

    def to_string(self):  # noqa: D102
        return "".join(event.to_string() for event in self.touch_events)

    def get_sum(self):  # noqa: D102
        sum = 0
        for touch_event in self.touch_events:
            sum += touch_event.type
            sum += touch_event.time
        return sum
