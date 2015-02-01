"""
homeassistant.util
~~~~~~~~~~~~~~~~~~

Helper methods for various modules.
"""
import collections
from itertools import chain
import threading
import queue
from datetime import datetime, timedelta
import re
import enum
import socket
import random
import string
from functools import wraps

RE_SANITIZE_FILENAME = re.compile(r'(~|\.\.|/|\\)')
RE_SANITIZE_PATH = re.compile(r'(~|\.(\.)+)')
RE_SLUGIFY = re.compile(r'[^A-Za-z0-9_]+')

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"


def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return RE_SANITIZE_FILENAME.sub("", filename)


def sanitize_path(path):
    """ Sanitizes a path by removing ~ and .. """
    return RE_SANITIZE_PATH.sub("", path)


def slugify(text):
    """ Slugifies a given text. """
    text = text.replace(" ", "_")

    return RE_SLUGIFY.sub("", text)


def datetime_to_str(dattim):
    """ Converts datetime to a string format.

    @rtype : str
    """
    return dattim.strftime(DATE_STR_FORMAT)


def str_to_datetime(dt_str):
    """ Converts a string to a datetime object.

    @rtype: datetime
    """
    try:
        return datetime.strptime(dt_str, DATE_STR_FORMAT)
    except ValueError:  # If dt_str did not match our format
        return None


def strip_microseconds(dattim):
    """ Returns a copy of dattime object but with microsecond set to 0. """
    if dattim.microsecond:
        return dattim - timedelta(microseconds=dattim.microsecond)
    else:
        return dattim


def split_entity_id(entity_id):
    """ Splits a state entity_id into domain, object_id. """
    return entity_id.split(".", 1)


def repr_helper(inp):
    """ Helps creating a more readable string representation of objects. """
    if isinstance(inp, dict):
        return ", ".join(
            repr_helper(key)+"="+repr_helper(item) for key, item
            in inp.items())
    elif isinstance(inp, datetime):
        return datetime_to_str(inp)
    else:
        return str(inp)


# Taken from: http://www.cse.unr.edu/~quiroz/inc/colortransforms.py
# License: Code is given as is. Use at your own risk and discretion.
# pylint: disable=invalid-name
def color_RGB_to_xy(R, G, B):
    """ Convert from RGB color to XY color. """
    if R + G + B == 0:
        return 0, 0

    var_R = (R / 255.)
    var_G = (G / 255.)
    var_B = (B / 255.)

    if var_R > 0.04045:
        var_R = ((var_R + 0.055) / 1.055) ** 2.4
    else:
        var_R /= 12.92

    if var_G > 0.04045:
        var_G = ((var_G + 0.055) / 1.055) ** 2.4
    else:
        var_G /= 12.92

    if var_B > 0.04045:
        var_B = ((var_B + 0.055) / 1.055) ** 2.4
    else:
        var_B /= 12.92

    var_R *= 100
    var_G *= 100
    var_B *= 100

    # Observer. = 2 deg, Illuminant = D65
    X = var_R * 0.4124 + var_G * 0.3576 + var_B * 0.1805
    Y = var_R * 0.2126 + var_G * 0.7152 + var_B * 0.0722
    Z = var_R * 0.0193 + var_G * 0.1192 + var_B * 0.9505

    # Convert XYZ to xy, see CIE 1931 color space on wikipedia
    return X / (X + Y + Z), Y / (X + Y + Z)


def convert(value, to_type, default=None):
    """ Converts value to to_type, returns default if fails. """
    try:
        return default if value is None else to_type(value)
    except ValueError:
        # If value could not be converted
        return default


def ensure_unique_string(preferred_string, current_strings):
    """ Returns a string that is not present in current_strings.
        If preferred string exists will append _2, _3, .. """
    test_string = preferred_string
    current_strings = list(current_strings)

    tries = 1

    while test_string in current_strings:
        tries += 1
        test_string = "{}_{}".format(preferred_string, tries)

    return test_string


# Taken from: http://stackoverflow.com/a/11735897
def get_local_ip():
    """ Tries to determine the local IP address of the machine. """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use Google Public DNS server to determine own IP
        sock.connect(('8.8.8.8', 80))
        ip_addr = sock.getsockname()[0]
        sock.close()

        return ip_addr

    except socket.error:
        return socket.gethostbyname(socket.gethostname())


# Taken from http://stackoverflow.com/a/23728630
def get_random_string(length=10):
    """ Returns a random string with letters and digits. """
    generator = random.SystemRandom()
    source_chars = string.ascii_letters + string.digits

    return ''.join(generator.choice(source_chars) for _ in range(length))


class OrderedEnum(enum.Enum):
    """ Taken from Python 3.4.0 docs. """
    # pylint: disable=no-init, too-few-public-methods

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class OrderedSet(collections.MutableSet):
    """ Ordered set taken from http://code.activestate.com/recipes/576694/ """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        """ Add an element to the end of the set. """
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def promote(self, key):
        """ Promote element to beginning of the set, add if not there. """
        if key in self.map:
            self.discard(key)

        begin = self.end[2]
        curr = begin[1]
        curr[2] = begin[1] = self.map[key] = [key, curr, begin]

    def discard(self, key):
        """ Discard an element from the set. """
        if key in self.map:
            key, prev_item, next_item = self.map.pop(key)
            prev_item[2] = next_item
            next_item[1] = prev_item

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):  # pylint: disable=arguments-differ
        """ Pops element of the end of the set.
            Set last=False to pop from the beginning. """
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def update(self, *args):
        """ Add elements from args to the set. """
        for item in chain(*args):
            self.add(item)

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


class Throttle(object):
    """
    A method decorator to add a cooldown to a method to prevent it from being
    called more then 1 time within the timedelta interval `min_time` after it
    returned its result.

    Calling a method a second time during the interval will return None.

    Pass keyword argument `no_throttle=True` to the wrapped method to make
    the call not throttled.

    Decorator takes in an optional second timedelta interval to throttle the
    'no_throttle' calls.

    Adds a datetime attribute `last_call` to the method.
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, min_time, limit_no_throttle=None):
        self.min_time = min_time
        self.limit_no_throttle = limit_no_throttle

    def __call__(self, method):
        lock = threading.Lock()

        if self.limit_no_throttle is not None:
            method = Throttle(self.limit_no_throttle)(method)

        @wraps(method)
        def wrapper(*args, **kwargs):
            """
            Wrapper that allows wrapped to be called only once per min_time.
            If we cannot acquire the lock, it is running so return None.
            """
            if lock.acquire(False):
                try:
                    last_call = wrapper.last_call

                    # Check if method is never called or no_throttle is given
                    force = not last_call or kwargs.pop('no_throttle', False)

                    if force or datetime.now() - last_call > self.min_time:

                        result = method(*args, **kwargs)
                        wrapper.last_call = datetime.now()
                        return result
                    else:
                        return None
                finally:
                    lock.release()

        wrapper.last_call = None

        return wrapper


class ThreadPool(object):
    """ A priority queue-based thread pool. """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, job_handler, worker_count=0, busy_callback=None):
        """
        job_handler: method to be called from worker thread to handle job
        worker_count: number of threads to run that handle jobs
        busy_callback: method to be called when queue gets too big.
                       Parameters: worker_count, list of current_jobs,
                                   pending_jobs_count
        """
        self._job_handler = job_handler
        self._busy_callback = busy_callback

        self.worker_count = 0
        self.busy_warning_limit = 0
        self._work_queue = queue.PriorityQueue()
        self.current_jobs = []
        self._lock = threading.RLock()
        self._quit_task = object()

        self.running = True

        for _ in range(worker_count):
            self.add_worker()

    def add_worker(self):
        """ Adds a worker to the thread pool. Resets warning limit. """
        with self._lock:
            if not self.running:
                raise RuntimeError("ThreadPool not running")

            worker = threading.Thread(target=self._worker)
            worker.daemon = True
            worker.start()

            self.worker_count += 1
            self.busy_warning_limit = self.worker_count * 3

    def remove_worker(self):
        """ Removes a worker from the thread pool. Resets warning limit. """
        with self._lock:
            if not self.running:
                raise RuntimeError("ThreadPool not running")

            self._work_queue.put(PriorityQueueItem(0, self._quit_task))

            self.worker_count -= 1
            self.busy_warning_limit = self.worker_count * 3

    def add_job(self, priority, job):
        """ Add a job to the queue. """
        with self._lock:
            if not self.running:
                raise RuntimeError("ThreadPool not running")

            self._work_queue.put(PriorityQueueItem(priority, job))

            # check if our queue is getting too big
            if self._work_queue.qsize() > self.busy_warning_limit \
               and self._busy_callback is not None:

                # Increase limit we will issue next warning
                self.busy_warning_limit *= 2

                self._busy_callback(
                    self.worker_count, self.current_jobs,
                    self._work_queue.qsize())

    def block_till_done(self):
        """ Blocks till all work is done. """
        self._work_queue.join()

    def stop(self):
        """ Stops all the threads. """
        with self._lock:
            if not self.running:
                return

            # Ensure all current jobs finish
            self.block_till_done()

            # Tell the workers to quit
            for _ in range(self.worker_count):
                self.remove_worker()

            self.running = False

            # Wait till all workers have quit
            self.block_till_done()

    def _worker(self):
        """ Handles jobs for the thread pool. """
        while True:
            # Get new item from work_queue
            job = self._work_queue.get().item

            if job == self._quit_task:
                self._work_queue.task_done()
                return

            # Add to current running jobs
            job_log = (datetime.now(), job)
            self.current_jobs.append(job_log)

            # Do the job
            self._job_handler(job)

            # Remove from current running job
            self.current_jobs.remove(job_log)

            # Tell work_queue the task is done
            self._work_queue.task_done()


class PriorityQueueItem(object):
    """ Holds a priority and a value. Used within PriorityQueue. """

    # pylint: disable=too-few-public-methods
    def __init__(self, priority, item):
        self.priority = priority
        self.item = item

    def __lt__(self, other):
        return self.priority < other.priority
