import logging
import sys

from voluptuous import Schema, Required, Any

from archivist.plugins import Notifier, log_level


class Plugin(Notifier):

    schema = Schema({
        'type': 'stream',
        Required('name'): Any('stdout', 'stderr'),
        'level': log_level,
        'fmt': str,
        'datefmt': str,
    })

    def __init__(self, type, name, level=logging.INFO, fmt=None, datefmt=None):
        super(Plugin, self).__init__(type, name, level, fmt, datefmt)
        self.handler = logging.StreamHandler(getattr(sys, name))
