""" Helper methods for various modules. """
import threading
import Queue
import datetime
import re

RE_SANITIZE_FILENAME = re.compile(r"(~|(\.\.)|/|\+)")
RE_SLUGIFY = re.compile(r'[^A-Za-z0-9_]+')

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"


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
        return ", ".join(
            repr_helper(key)+"="+repr_helper(item) for key, item in inp.items()
            )
    elif isinstance(inp, list):
        return '[' + ', '.join(inp) + ']'
    elif isinstance(inp, datetime.datetime):
        return datetime_to_str(inp)
    else:
        return str(inp)


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
