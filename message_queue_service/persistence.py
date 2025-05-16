import json
import os

PERSISTENCE_FILE = os.environ.get("PERSISTENCE_FILE", "queues.json")

def save_state(queues):
    """
    Save the current state of queues to a JSON file.
    """
    with open(PERSISTENCE_FILE, "w") as f:
        json.dump(queues, f)

def load_state():
    """
    Load the state of queues from a JSON file.
    If the file does not exist, return an empty dictionary.
    """
    if os.path.exists(PERSISTENCE_FILE):
        with open(PERSISTENCE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # Handle the case where the file is empty or corrupted
                return {}
    return {}