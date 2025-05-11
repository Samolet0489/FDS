import threading
from persistence import load_state, save_state

class QueueManager:
    def __init__(self, max_size=100):
        """
        Initialize the QueueManager with an optional maximum queue size.
        Loads existing queues from persistent storage.
        """
        self.lock = threading.Lock()
        self.queues = load_state()
        self.max_queue_size = max_size

    def create_queue(self, name):
        """
        Create a new empty queue with the given name.
        Raises Exception if the queue already exists.
        """
        with self.lock:
            if name in self.queues:
                raise Exception(f"Queue '{name}' already exists")
            self.queues[name] = []

    def delete_queue(self, name):
        """
        Delete the queue and all its messages.
        Raises Exception if the queue does not exist.
        """
        with self.lock:
            if name not in self.queues:
                raise Exception(f"Queue '{name}' does not exist")
            del self.queues[name]

    def list_queues(self):
        """
        Return a list of all existing queue names.
        """
        with self.lock:
            return list(self.queues.keys())

    def push(self, name, message):
        """
        Append a message to the end of the specified queue.
        Raises Exception if queue not found or at max capacity.
        """
        with self.lock:
            if name not in self.queues:
                raise Exception(f"Queue '{name}' does not exist")
            if len(self.queues[name]) >= self.max_queue_size:
                raise Exception(f"Queue '{name}' is full (max {self.max_queue_size})")
            self.queues[name].append(message)

    def pull(self, name):
        """
        Remove and return the oldest message from the specified queue.
        Raises Exception if queue not found or empty.
        """
        with self.lock:
            if name not in self.queues:
                raise Exception(f"Queue '{name}' does not exist")
            if not self.queues[name]:
                raise Exception(f"Queue '{name}' is empty")
            return self.queues[name].pop(0)

    def persist(self):
        """
        Save current queues to persistent storage.
        """
        with self.lock:
            save_state(self.queues)
