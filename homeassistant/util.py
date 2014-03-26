""" Helper methods for various modules. """
import threading
import Queue
import datetime
import re

RE_SANITIZE_FILENAME = re.compile(r'(~|\.\.|/|\\)')
RE_SLUGIFY = re.compile(r'[^A-Za-z0-9_]+')

DATE_STR_FORMAT = u"%H:%M:%S %d-%m-%Y"


def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return RE_SANITIZE_FILENAME.sub("", filename)


def slugify(text):
    """ Slugifies a given text. """
    text = text.strip().replace(" ", "_")

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


def filter_entity_ids(entity_ids, domain_filter=None, strip_domain=False):
    """ Filter a list of entities based on domain. Setting strip_domain
        will only return the object_ids. """
    return [
        split_entity_id(entity_id)[1] if strip_domain else entity_id
        for entity_id in entity_ids if
        not domain_filter or entity_id.startswith(domain_filter)
        ]


def repr_helper(inp):
    """ Helps creating a more readable string representation of objects. """
    if isinstance(inp, dict):
        return u", ".join(
            repr_helper(key)+u"="+repr_helper(item) for key, item
            in inp.items())
    elif isinstance(inp, datetime.datetime):
        return datetime_to_str(inp)
    else:
        return unicode(inp)


# Taken from: http://www.cse.unr.edu/~quiroz/inc/colortransforms.py
# License: Code is given as is. Use at your own risk and discretion.
# pylint: disable=invalid-name
def color_RGB_to_xy(R, G, B):
    ''' Convert from RGB color to XY color. '''
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

    while preferred_string in current_strings:
        tries += 1
        string = "{}_{}".format(preferred_string, tries)

    return string


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

    # pylint: disable=too-few-public-methods
    def __init__(self, worker_count, job_handler):
        queue = self.queue = Queue.PriorityQueue()
        current_jobs = self.current_jobs = []

        for _ in xrange(worker_count):
            worker = threading.Thread(target=_threadpool_worker,
                                      args=(queue, current_jobs, job_handler))
            worker.daemon = True
            worker.start()

    def add_job(self, priority, job):
        """ Add a job to be sent to the workers. """
        self.queue.put((priority, job))


def _threadpool_worker(queue, current_jobs, job_handler):
    """ Provides the base functionality of a worker for the thread pool. """
    while True:
        # Get new item from queue
        job = queue.get()[1]

        # Add to current running jobs
        job_log = (datetime.datetime.now(), job)
        current_jobs.append(job_log)

        # Do the job
        job_handler(job)

        # Remove from current running job
        current_jobs.remove(job_log)

        # Tell queue a task is done
        queue.task_done()
