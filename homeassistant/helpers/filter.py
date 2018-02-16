"""Deprecation helpers for Home Assistant."""
import logging
import inspect
import statistics
from collections import deque

DEFAULT_WINDOW_SIZE = 5
FILTER_LOWPASS = 1
FILTER_OUTLIER = 2
FILTERS = [FILTER_LOWPASS, FILTER_OUTLIER]

class Filter(object):
    """Filter outlier states, and smooth things out."""

    def __init__(self, filter_algorithm, window_size=DEFAULT_WINDOW_SIZE):
        """Decorator constructor, selects algorithm and configures windows."""
        module_name = inspect.getmodule(inspect.stack()[1][0]).__name__
        self.logger = logging.getLogger(module_name)
        self.logger.debug("Filter %s on %s", filter_algorithm, module_name)
        self.filter = None
        self.states = deque(maxlen=window_size)

        if filter_algorithm in FILTERS:
            if filter_algorithm == FILTER_LOWPASS:
                self.filter = self._lowpass
            elif filter_algorithm == FILTER_OUTLIER:
                self.filter = self._outlier
        else:
            self.logger.error("Unknown filter <%s>", filter_algorithm)
            return

    def __call__(self, func):
        """Decorate function as deprecated."""
        logger = self.logger
        states = self.states
        filter_algo = self.filter

        if len(self.states):
            last_state = self.states[-1]
        else:
            last_state = None

        def func_wrapper(self):
            """Wrap for the original function."""
            new_state = func(self)
            try:
                filtered_state = filter_algo(float(new_state), states) #float might not be appropriate
            except TypeError:
                return None
            except ValueError as e:
                logger.debug("Invalid Value: %s, reason: %s", float(new_state), e)
                return last_state
            states.append(filtered_state)
            logger.debug("new_state = %s    | filtered_state = %s", new_state, filtered_state)
            return filtered_state

        return func_wrapper

    @staticmethod
    def _outlier(new_state, states, constant=10):
        """BASIC outlier filter."""
        if (len(states) > 1 and 
            abs(new_state - statistics.median(states)) > 
            constant*statistics.stdev(states)):
            raise ValueError("Outlier detected")
        return new_state

    @staticmethod
    def _lowpass(new_state, states, time_constant=4):
        """BASIC Low Pass Filter."""
        try:
            B = 1.0 / time_constant
            A = 1.0 - B
            filtered = A * states[-1] + B * new_state
        except IndexError:
            # if we don't have enough states to run the filter
            # just accept the new value
            filtered = new_state
        return round(filtered, 2)
