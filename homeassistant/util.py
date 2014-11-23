"""
homeassistant.util
~~~~~~~~~~~~~~~~~~

Helper methods for various modules.
"""
import threading
import queue
import datetime
import re
import enum
import socket

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
        return datetime.datetime.strptime(dt_str, DATE_STR_FORMAT)
    except ValueError:  # If dt_str did not match our format
        return None


def split_entity_id(entity_id):
    """ Splits a state entity_id into domain, object_id. """
    return entity_id.split(".", 1)


def repr_helper(inp):
    """ Helps creating a more readable string representation of objects. """
    if isinstance(inp, dict):
        return ", ".join(
            repr_helper(key)+"="+repr_helper(item) for key, item
            in inp.items())
    elif isinstance(inp, datetime.datetime):
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
    string = preferred_string

    tries = 1

    while string in current_strings:
        tries += 1
        string = "{}_{}".format(preferred_string, tries)

    return string


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


def validate_config(config, items, logger):
    """
    Validates if all items are available in the configuration.

    config is the general dictionary with all the configurations.
    items is a dict with per domain which attributes we require.
    logger is the logger from the caller to log the errors to.

    Returns True if all required items were found.
    """
    errors_found = False
    for domain in items.keys():
        errors = [item for item in items[domain] if item not in config[domain]]

        if errors:
            logger.error(
                "Missing required configuration items in {}: {}".format(
                    domain, ", ".join(errors)))

            errors_found = True

    return not errors_found


# Reason why I decided to roll my own ThreadPool instead of using
# multiprocessing.dummy.pool or even better, use multiprocessing.pool and
# not be hurt by the GIL in the cpython interpreter:
# 1. The built in threadpool does not allow me to create custom workers and so
#    I would have to wrap every listener that I passed into it with code to log
#    the exceptions. Saving a reference to the logger in the worker seemed
#    like a more sane thing to do.
# 2. Most event listeners are simple checks if attributes match. If the method
#    that they will call takes a long time to complete it might be better to
#    put that request in a seperate thread. This is for every component to
#    decide on its own instead of enforcing it for everyone.
class ThreadPool(object):
    """ A simple queue-based thread pool.

    Will initiate it's workers using worker(queue).start() """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, worker_count, job_handler, busy_callback=None):
        """
        worker_count: number of threads to run that handle jobs
        job_handler: method to be called from worker thread to handle job
        busy_callback: method to be called when queue gets too big.
                       Parameters: list_of_current_jobs, number_pending_jobs
        """
        self.work_queue = work_queue = queue.PriorityQueue()
        self.current_jobs = current_jobs = []
        self.worker_count = worker_count
        self.busy_callback = busy_callback
        self.busy_warning_limit = worker_count**2
        self._lock = threading.RLock()
        self._quit_task = object()

        for _ in range(worker_count):
            worker = threading.Thread(target=_threadpool_worker,
                                      args=(work_queue, current_jobs,
                                            job_handler, self._quit_task))
            worker.daemon = True
            worker.start()

        self.running = True

    def add_job(self, priority, job):
        """ Add a job to be sent to the workers. """
        with self._lock:
            if not self.running:
                raise Exception("We are shutting down the ")

            self.work_queue.put(PriorityQueueItem(priority, job))

            # check if our queue is getting too big
            if self.work_queue.qsize() > self.busy_warning_limit \
               and self.busy_callback is not None:

                # Increase limit we will issue next warning
                self.busy_warning_limit *= 2

                self.busy_callback(self.current_jobs, self.work_queue.qsize())

    def block_till_done(self):
        """ Blocks till all work is done. """
        self.work_queue.join()

    def stop(self):
        """ Stops all the threads. """
        with self._lock:
            if not self.running:
                return

            # Clear the queue
            while self.work_queue.qsize() > 0:
                self.work_queue.get()
                self.work_queue.task_done()

            # Tell the workers to quit
            for _ in range(self.worker_count):
                self.add_job(1000, self._quit_task)

            self.running = False

            self.block_till_done()


class PriorityQueueItem(object):
    """ Holds a priority and a value. Used within PriorityQueue. """

    # pylint: disable=too-few-public-methods
    def __init__(self, priority, item):
        self.priority = priority
        self.item = item

    def __lt__(self, other):
        return self.priority < other.priority


def _threadpool_worker(work_queue, current_jobs, job_handler, quit_task):
    """ Provides the base functionality of a worker for the thread pool. """
    while True:
        # Get new item from work_queue
        job = work_queue.get().item

        if job == quit_task:
            work_queue.task_done()
            return

        # Add to current running jobs
        job_log = (datetime.datetime.now(), job)
        current_jobs.append(job_log)

        # Do the job
        job_handler(job)

        # Remove from current running job
        current_jobs.remove(job_log)

        # Tell work_queue a task is done
        work_queue.task_done()
