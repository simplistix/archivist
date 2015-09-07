import logging
import sys
from voluptuous import Schema, Required, Any, Invalid
from archivist.plugins import Notifier

logger = logging.getLogger()


def log_level(value):
    try:
        return int(value)
    except ValueError:
        level = getattr(logging, value.upper(), None)
        if level is None:
            raise Invalid('no log level named %r' % value)
        return level


class Plugin(Notifier):

    schema = Schema({
        'type': 'stream',
        Required('name'): Any('stdout', 'stderr'),
        Required('level', default=logging.INFO): log_level,
        Required('fmt', default=None): str,
        Required('datefmt', default=None): str,
    })

    def __init__(self, type, name, level, fmt, datefmt):
        super(Plugin, self).__init__(type, name)
        self.stream = getattr(sys, name)
        self.level = level
        self.fmt = fmt
        self.datefmt = datefmt

    def start(self):
        handler = self.handler = logging.StreamHandler(self.stream)
        if self.fmt or self.datefmt:
            handler.setFormatter(logging.Formatter(self.fmt, self.datefmt))
        handler.setLevel(self.level)
        logger.setLevel(self.level)
        logger.addHandler(handler)

    def finish(self):
        logger.removeHandler(self.handler)
