from abc import ABCMeta, abstractmethod, abstractproperty
from collections import defaultdict
from pkg_resources import iter_entry_points


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
    def __init__(self, type, name, **config):
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

    @abstractmethod
    def __init__(self, type, name, repo, **config):
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


class Notifier(Plugin):

    @abstractmethod
    def start(self):
        """
        Install necessary log handlers.
        """

    @abstractmethod
    def finish(self):
        """
        Do any clean up or finalisation needed for the notifications.
        """
