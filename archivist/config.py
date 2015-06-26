from voluptuous import (
    Schema, Required, MultipleInvalid, Length, All, Any, Extra
)
import yaml


class ConfigError(Exception):

    def __init__(self, errors, config):
        self.errors = errors
        self.config = config

    def resolve_path(self, error):
        resolved = []
        unresolved = list(error.path)
        config = self.config
        while unresolved:
            element = unresolved[0]
            try:
                config = config[element]
            except (IndexError, KeyError):
                break
            else:
                resolved.append(element)
                unresolved.pop(0)
        return resolved, config, unresolved

    @staticmethod
    def format_path(path):
        return repr(path) if path else 'root'

    @staticmethod
    def sort_key(e):
        return map(str, e.path)

    def handle_list(self, errors):
        for error in sorted(self.errors, key=self.sort_key):

            path, config, unresolved = self.resolve_path(error)

            parts = ['at '+self.format_path(path), error.message]
            if unresolved:
                parts.append(self.format_path(unresolved[0]))
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


default_repo_config = dict(
    type='git',
    name='config',
    path='/var/archivist'
)

default_notifications_config = dict(
    type='pipe',
    value='stderr'
)


plugin_schema = Any(
    All(dict, Length(max=1)),
    {Required('type'): str, Extra: object}
)

schema = Schema({
    Required('repos',
             default=[default_repo_config]): [plugin_schema],
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
    def check_schema(raw):
        try:
            return schema(raw)
        except MultipleInvalid as e:
            raise ConfigError(e.errors, raw)

    @staticmethod
    def normalise_plugin_config(data):
        """
        Turn {'foo': 'bar'} into {'type': 'foo', 'value': 'bar'}
        """
        for values in data.values():
            for index, value in enumerate(values):
                if len(value) == 1:
                    key, value = value.items()[0]
                    values[index] = dict(type=key, value=value)
        return data

    @classmethod
    def parse(cls, source):
        """
        Read an open file into a valid, nested dict.
        Raises a :class:`ConfigError` if the data isn't valid.
        """
        raw = yaml.load(source)
        data = cls.check_schema(raw)
        data = cls.normalise_plugin_config(data)
        return data
