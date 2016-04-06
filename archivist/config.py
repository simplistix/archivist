from collections import defaultdict
from inspect import getargspec
from voluptuous import (
    Schema, Required, MultipleInvalid, Length, All, Any, Extra
)
import yaml
from archivist.plugins import Repo, Notifier, Source


class ConfigError(Exception):

    def __init__(self, errors, config, path=None):
        self.errors = errors
        self.config = config
        self.path = path

    def resolve_path(self, error):
        resolved = []
        unresolved = list(error.path)
        config = context_config = self.config
        while unresolved:
            element = unresolved[0]
            try:
                context_config = config
                config = config[element]
            except (IndexError, KeyError):
                break
            else:
                resolved.append(element)
                unresolved.pop(0)
        return resolved, context_config, unresolved

    @staticmethod
    def sort_key(e):
        return map(str, e.path)

    def handle_list(self, errors):
        for error in sorted(self.errors, key=self.sort_key):

            path, config, unresolved = self.resolve_path(error)
            if self.path is not None:
                path = self.path + path
            parts = ['at ' + (repr(path) if path else 'root'), error.msg]
            if unresolved:
                parts.append(repr(unresolved[0]))
            message = ', '.join(parts)

            yield message, config

    def handle_str(self, message):
        yield message, self.config

    def __str__(self):
        handler = getattr(self, 'handle_'+type(self.errors).__name__)
        output = []
        for message, config in handler(self.errors):
            output.append('{message}: \n{yaml}'.format(
                message=message,
                yaml=yaml.dump(config, default_flow_style=False)
            ))
        return '\n'.join(output)

default_config_name = getargspec(Repo.__init__).keywords

default_repo_config = dict(
    type='git',
    name=default_config_name,
    path='/var/archivist'
)

default_notifications_config = dict(
    type='stream',
    name='stderr'
)


plugin_schema = Any(
    All(dict, Length(max=1)),
    {Required('type'): str, Extra: object}
)

repo_schema = {Required('type'): str,
               Required('name'): str,
               Extra: object}

schema = Schema({
    Required('repos',
             default=[default_repo_config]): [repo_schema],
    Required('sources'): All([plugin_schema], Length(1)),
    Required('notifications',
             default=[default_notifications_config]): [plugin_schema],
})


class Config(object):

    def __init__(self):
        self.repos = {}
        self.sources = []
        self.notifications = []

    @staticmethod
    def check_schema(raw, schema=schema, path=None):
        try:
            return schema(raw)
        except MultipleInvalid as e:
            raise ConfigError(e.errors, raw, path)

    @staticmethod
    def normalise_plugin_config(data):
        """
        Config transformations:
        - ``{'foo': 'bar'}`` to ``{'type': 'foo', 'name': 'bar'}``
        - ``{'type': 'foo', 'value': 'bar'}`` to
          ``{'type': 'foo', 'value': 'bar', 'name': None}``
        - ``{'foo': ['bar', 'baz']}`` to
          ``{type: 'foo', 'name': None, 'value':['bar', 'baz']}``
        """
        for values in data.values():
            for index, value in enumerate(values):
                if len(value) == 1:
                    key, value = value.items()[0]
                    values[index] = new_value = dict(type=key)
                    if isinstance(value, str):
                        new_value['name'] = value
                    else:
                        new_value['values'] = value
                    value = new_value
                if 'name' not in value:
                    value['name'] = None
        return data

    @staticmethod
    def check_source_repos(data):
        repo_names = set(config['name'] for config in data['repos'])
        for config in data['sources']:
            if 'repo' in config:
                if config['repo'] not in repo_names:
                    raise ConfigError(
                        'source specifies invalid repo {!r}'.format(config['repo']),
                        config
                    )
            else:
                repo = default_repo_config['name']
                if repo not in repo_names:
                    raise ConfigError(
                        'source specifies no repo and the default repo, '
                        '{!r}, is not configured'.format(repo),
                        config
                    )
                config['repo'] = default_repo_config['name']

    @staticmethod
    def check_source_names(data):
        seen = defaultdict(set)
        for source in data['sources']:
            name = source.get('name')
            type_ = source['type']
            if name in seen[type_]:
                raise ConfigError(
                    'more than one source of type {!r} named {!r}'.format(
                        type_, name
                    ),
                    source
                )
            seen[type_].add(name)

    @classmethod
    def parse(cls, source):
        """
        Read an open file into a valid, nested dict.
        Raises a :class:`ConfigError` if the data isn't valid.
        """
        raw = yaml.load(source)
        data = cls.check_schema(raw)
        data = cls.normalise_plugin_config(data)
        cls.check_source_repos(data)
        cls.check_source_names(data)
        return data

    @staticmethod
    def load_plugin(plugins, type_, name, config, abc):
        try:
            plugin_class = plugins.get(type_, name)
        except KeyError:
            raise ConfigError(
                'No plugin found for {} of type {!r}'.format(
                    type_, name
                ),
                config
            )
        if not issubclass(plugin_class, abc):
            raise TypeError('{} is not a {}'.format(
                plugin_class, abc
            ))
        return plugin_class

    @classmethod
    def realise(cls, config_data, plugins):
        """
        Turns a config dict and a plugin registry into a fully
        formed :class:`Config`.
        Raises a :class:`ConfigError` if the plugins can't be found.
        """
        config = Config()
        for plugin_type_p, plugin_abc in (
                ('repos', Repo),
                ('sources', Source),
                ('notifications', Notifier)
        ):
            plugin_type = plugin_type_p[:-1]

            for plugin_index, plugin_config in enumerate(
                    config_data[plugin_type_p]
            ):

                config_path = [plugin_type_p, plugin_index]

                plugin_name = plugin_config['type']

                plugin_class = cls.load_plugin(plugins,
                                               plugin_type, plugin_name,
                                               plugin_config, plugin_abc)
                plugin_config = cls.check_schema(plugin_config,
                                                 plugin_class.schema,
                                                 config_path)

                plugin = plugin_class(**plugin_config)
                store = getattr(config, plugin_type_p)
                if plugin_type_p == 'repos':
                    store[plugin_config['name']] = plugin
                else:
                    store.append(plugin)

        return config

    @classmethod
    def load(cls, source, plugins):
        """
        Create a :class:`Config` from a source file object and a
        :class:`Plugins` registry.
        """
        return cls.realise(cls.parse(source), plugins)

    def repo_for(self, source):
        return self.repos[source.repo]
