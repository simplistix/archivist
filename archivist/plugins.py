from abc import ABCMeta, abstractmethod, abstractproperty
from collections import defaultdict
import logging
from pkg_resources import iter_entry_points
from voluptuous import Invalid


class Plugins(object):
    "Registry for Plugin classes"

    def __init__(self):
        self.plugins = defaultdict(dict)

    @classmethod
    def load(cls):
        """
        Load plugins from entrypoints specified in packages and register them
        """
        plugins = Plugins()
        for type in 'notification', 'repo', 'source':
            for entrypoint in iter_entry_points(group='archivist.'+type):
                plugin = entrypoint.load()
                plugins.register(type, entrypoint.name, plugin)
        return plugins

    def register(self, type, name, plugin):
        "Register an individual plugin"
        self.plugins[type][name] = plugin

    def get(self, type, name):
        """
        Get a plugin from the registry, raising :class:`KeyError` if a
        plugin of the supplied name has not been registered.
        """
        return self.plugins[type][name]


class Plugin(object):

    __metaclass__ = ABCMeta

    @abstractproperty
    def schema(self):
        """
        This attribute should be a :class:`voluptuous.Schema` instance
        that will be used to validate configuration information passed
        to the plugin's constructor.
        """

    @abstractmethod
    def __init__(self, type, name=None, **config):
        """
        :param type: string name of the type of plugin this is.
        :param name: string name of this plugin, which may be ``None``.
        :param config: a dict containing the config for this instance
                       of the plugin.
        """
        self.type = type
        self.name = name


class Repo(Plugin):

    @abstractmethod
    def path_for(self, source):
        """
        :param source: a :class:`Source` instance.

        :return: An absolute path to a directory where sources can write.
                 This does not need to be empty and may be temporary.
                 It must, however, exist and be writeable.
        """

    @abstractmethod
    def actions(self):
        """
        Perform the required actions after all sources have been processed.
        These may include making a commit containing changes recorded by
        sources or logging them by way of the standard library logging
        framework.
        """


class Source(Plugin):

    def __init__(self, type, name=None, repo='config',
                 **config):
        """
        :param type: string name of the type of plugin this is.
        :param repo: string name of the repo this source will use.
        :param config: a dict containing the config for this instance
                       of the plugin.
        """
        super(Source, self).__init__(type, name)
        self.repo = repo

    @abstractmethod
    def process(self, path):
        """
        Record information as specified in the plugin's configuration.

        :param path: An absolute path to a directory in which information
                     should be recorded.
        """


logger = logging.getLogger()


def log_level(value):
    try:
        return int(value)
    except ValueError:
        level = getattr(logging, value.upper(), None)
        if level is None:
            raise Invalid('no log level named %r' % value)
        return level


class Notifier(Plugin):

    handler = None
    """
    This attribute should be a :class:`logging.Handler` instance
    that will be used to handle logging from other plugins.

    It should be set up in :meth:`__init__`.
    """

    @abstractmethod
    def __init__(self, type, name, level, fmt, datefmt):
        super(Notifier, self).__init__(type, name)
        self.level = level
        self.fmt = fmt
        self.datefmt = datefmt

    def start(self):
        """
        Install necessary log handlers.
        """
        if self.fmt or self.datefmt:
            self.handler.setFormatter(logging.Formatter(self.fmt, self.datefmt))
        self.handler.setLevel(self.level)
        logger.setLevel(self.level)
        logger.addHandler(self.handler)

    def finish(self):
        """
        Do any clean up or finalisation needed for the notifications.
        """
        self.handler.close()
        logger.removeHandler(self.handler)
