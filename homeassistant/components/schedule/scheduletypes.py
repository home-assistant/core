"""Aliases for types used in schedule parsing."""

from datetime import time
from typing import List, Tuple

# Pylint currently doesn't understand that type aliases should be treated as
# classes
# pylint: disable=C0103
State = str

# At time t change state to s
ScheduleEvent = Tuple[time, State]

# On days xyz do state changes abc
ScheduleEntry = Tuple[List[int], List[ScheduleEvent]]
