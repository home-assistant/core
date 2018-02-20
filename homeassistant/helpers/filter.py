"""Filter helpers for Home Assistant."""
import logging
import inspect
import statistics
from collections import deque
from homeassistant.util.decorator import Registry

DEFAULT_WINDOW_SIZE = 5
FILTER_LOWPASS = 'lowpass'
FILTER_OUTLIER = 'outlier'

FILTERS = Registry()


class Filter(object):
    """Filter decorator."""

    logger = None
    sensor_name = None

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
        Filter.logger.debug("Filter %s(%s) on %s", filter_algorithm, kwargs,
                            module_name)
        self.filter_args = kwargs
        self.filter_stats = {'filter': filter_algorithm}
        self.states = deque(maxlen=window_size)

        if filter_algorithm in FILTERS:
            self.filter = FILTERS[filter_algorithm]
        else:
            self.logger.error("Unknown filter <%s>", filter_algorithm)
            return

    def __call__(self, func):
        """Decorate function as filter."""
        def func_wrapper(sensor_object):
            """Wrap for the original state() function."""
            Filter.sensor_name = sensor_object.entity_id
            new_state = func(sensor_object)
            try:
                filtered_state = self.filter(new_state=float(new_state),
                                             stats=self.filter_stats,
                                             states=self.states,
                                             **self.filter_args)
            except TypeError:
                return None

            self.states.append(filtered_state)

            """ filter_stats makes available few statistics to the sensor """
            sensor_object.filter_stats = self.filter_stats

            Filter.logger.debug("%s(%s) -> %s", self.filter_stats['filter'],
                                new_state, filtered_state)
            return filtered_state

        return func_wrapper


@FILTERS.register(FILTER_OUTLIER)
def _outlier(new_state, stats, states, **kwargs):
    """BASIC outlier filter.

    Determines if new state in a band around the median

    Args:
        new_state (float): new value to the series
        stats (dict): used to feedback stats on the filter
        states (deque): previous data series
        constant (int): median multiplier/band range

    Returns:
        the original new_state case not an outlier
        the median of the window case it's an outlier

    """
    constant = kwargs.pop('constant', 0.10)
    erasures = stats.get('erasures', 0)

    if (len(states) > 1 and
            abs(new_state - statistics.median(states)) >
            constant*statistics.median(states)):

        stats['erasures'] = erasures+1
        Filter.logger.warning("Outlier in %s: %s",
                              Filter.sensor_name, float(new_state))
        return statistics.median(states)
    return new_state


@FILTERS.register(FILTER_LOWPASS)
def _lowpass(new_state, stats, states, **kwargs):
    """BASIC Low Pass Filter.

    Args:
        new_state (float): new value to the series
        stats (dict): used to feedback stats on the filter
        states (deque): previous data series
        time_constant (int): time constant.

    Returns:
        a new state value that has been smoothed by filter

    """
    time_constant = kwargs.pop('time_constant', 4)
    precision = kwargs.pop('precision', None)

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

    if precision is None:
        return filtered
    else:
        return round(filtered, precision)
