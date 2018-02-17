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

    logger = None

    def __init__(self, filter_algorithm, window_size=DEFAULT_WINDOW_SIZE,
                 **kwargs):
        """Decorator constructor, selects algorithm and configures window.

        Args:
            filter_algorithm (int): must be one of the defined filters
            window_size (int): size of the sliding window that holds previous
                                values
            kwargs (dict): arguments to be passed to the specific filter

        """
        module_name = inspect.getmodule(inspect.stack()[1][0]).__name__
        Filter.logger = logging.getLogger(module_name)
        Filter.logger.debug("Filter %s on %s", filter_algorithm, module_name)
        self.filter = None
        self.filter_args = kwargs
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
        """Decorate function as filter."""
        states = self.states
        filter_algo = self.filter
        filter_args = self.filter_args

        if len(self.states):
            last_state = self.states[-1]
        else:
            last_state = None

        def func_wrapper(self):
            """Wrap for the original state() function."""
            new_state = func(self)
            try:
                Filter.logger.debug("Filter arguments: %s", filter_args)
                filtered_state = filter_algo(new_state=float(new_state),
                                             states=states, **filter_args)
            except TypeError:
                return None
            except ValueError as e:
                Filter.logger.warning("Invalid Value in %s: %s, reason: %s",
                                      self.entity_id, float(new_state), e)
                return last_state
            states.append(filtered_state)
            Filter.logger.debug("%s(%s) -> %s", filter_algo.__name__,
                                new_state, filtered_state)
            return filtered_state

        return func_wrapper

    @staticmethod
    def _outlier(new_state, states, **kwargs):
        """BASIC outlier filter.
   
        Will through a ValueError indicating an outlier value
        that should not be published, else the current value.

        Args:
            new_state (float): new value to the series
            states (deque): previous data series
            constant (int): stdev multiplier.

        Returns:
            the original new_state

        """
        constant = kwargs.pop('constant', 10)

        if (len(states) > 1 and
                abs(new_state - statistics.median(states)) >
                constant*statistics.stdev(states)):
            raise ValueError("Outlier detected")
        return new_state

    @staticmethod
    def _lowpass(new_state, states, **kwargs):
        """BASIC Low Pass Filter.

        Args:
            new_state (float): new value to the series
            states (deque): previous data series
            time_constant (int): time constant.

        Returns:
            a new state value that has been smoothed by filter

        """
        time_constant = kwargs.pop('time_constant', 4)
        if len(kwargs) != 0:
            Filter.logger.error("unrecognized params passed in: %s", kwargs)

        try:
            B = 1.0 / time_constant
            A = 1.0 - B
            filtered = A * states[-1] + B * new_state
        except IndexError:
            # if we don't have enough states to run the filter
            # just accept the new value
            filtered = new_state
        return round(filtered, 2)
