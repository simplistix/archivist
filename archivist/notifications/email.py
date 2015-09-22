import logging

from voluptuous import Schema, Required, Invalid

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
        'type': 'email',
        Required('name'): None,
        'level': log_level,
        'fmt': str,
        'datefmt': str,
        'sender': str,
        Required('recipient'): str,
        'mailhost': str,
        'username': str,
        'password': str,
        'headers': {str: str},
        'send_level': log_level,
    })

    def __init__(self, type, name, recipient, sender=None,
                 level=logging.INFO, fmt=None, datefmt=None, **kw):
        super(Plugin, self).__init__(type, name, level, fmt, datefmt)
        # import here to make mailinglogger optional
        from mailinglogger import SummarisingLogger
        self.handler = SummarisingLogger(
            fromaddr=sender or recipient,
            toaddrs=[recipient],
            subject='Archivist Notification (%(levelname)s)',
            send_empty_entries=False,
            atexit=False,
            **kw
        )
