from unittest import TestCase
from testfixtures import TempDirectory, compare, ShouldRaise, Comparison as C
from voluptuous import Required, Schema, ALLOW_EXTRA
from archivist.config import (
    Config, ConfigError, default_repo_config,
    default_notifications_config
)
from archivist.plugins import (
    Plugins, Repo, Source, Notifier
)


def config(item):
    return dict(test=[item])

class TestNormalisation(TestCase):

    def test_key_value_to_type_name(self):
        compare(config({'type': 'foo', 'name': 'bar'}),
                Config.normalise_plugin_config(
                    config({'foo': 'bar'})
                ))

    def test_no_name(self):
        compare(config({'type': 'foo', 'value': 'bar', 'name': None}),
                Config.normalise_plugin_config(
                    config({'type': 'foo', 'value': 'bar'})
                ))

    def test_list_value(self):
        compare(config({'type': 'foo', 'name': None, 'values':['bar', 'baz']}),
                Config.normalise_plugin_config(
                    config({'foo': ['bar', 'baz']})
                ))


class WithTempDir(object):

    def setUp(self):
        self.dir = TempDirectory()

    def tearDown(self):
        self.dir.cleanup()


class TestParse(WithTempDir, TestCase):

    def check_config_error(self, text, expected):
        source = open(self.dir.write('test.yaml', text))
        with ShouldRaise(ConfigError) as s:
            Config.parse(source)
        compare(expected, str(s.raised), trailing_whitespace=False)

    def check_parses(self, text, expected):
        source = open(self.dir.write('test.yaml', text))
        actual = Config.parse(source)
        compare(expected, actual)

    def test_okay(self):
        self.check_parses("""
repos:
  - name: config
    type: git

sources:
- path: /some/path
- crontab: root
# a comment
- type: jenkins
  username: foo
  password: bar

notifications:
- email: test@example.com
""", dict(
            repos=[
                dict(name='config', type='git')
            ],
            sources=[
                dict(type='path', name='/some/path', repo='config'),
                dict(type='crontab', name='root', repo='config'),
                dict(type='jenkins', username='foo', password='bar',
                     repo='config', name=None),
            ],
            notifications=[
                dict(type='email', name='test@example.com')
            ],
        ))

    def test_empty(self):
        self.check_config_error('', 'at root, expected a dictionary: \n'
                                    'null\n'
                                    '...\n')

    def test_not_mapping(self):
        self.check_config_error(
            '''
- one
- two
''',
            'at root, expected a dictionary: \n'
            '- one\n'
            '- two\n'
        )

    def test_unexpected_and_missing_keys(self):
        self.check_config_error(
            '''
one:
  - two
''',
            '''\
at ['one'], extra keys not allowed:
one:
- two

at root, required key not provided, 'sources':
one:
- two

''')

    def test_invalid_repos(self):
        # not a list
        self.check_config_error(
            """
notifications:
- some: thing
sources:
- some: thing
repos:
  name: config
  type: git
""",
            '''\
at ['repos'], expected a list:
notifications:
- some: thing
repos:
  name: config
  type: git
sources:
- some: thing
''')

    def test_invalid_repo(self):
        # not a mapping
        self.check_config_error(
            """
notifications:
- some: thing
sources:
- some: thing
repos:
  [['foo', 'bar']]
""",
            '''\
at ['repos', 0], invalid list value:
- - foo
  - bar
''')

    def test_repo_defaults(self):
        self.check_parses(
            """
notifications:
- some: thing
sources:
- some: thing
""",
            dict(
                notifications=[
                    dict(type='some', name='thing')
                ],
                repos=[default_repo_config],
                sources=[
                    dict(type='some', name='thing', repo='config')
                ]
            ))

    def test_repo_missing_name(self):
        self.check_config_error(
            """
repos:
  - git: foo

sources:
- path: /some/path
""",
            '''\
at ['repos', 0], required key not provided, 'name':
git: foo
at ['repos', 0], required key not provided, 'type':
git: foo''')

    def test_no_sources(self):
        self.check_config_error(
            """
notifications:
- some: thing
sources: []
""",
            '''\
at ['sources'], length of value must be at least 1:
notifications:
- some: thing
sources: []
 ''')

    def test_invalid_sources(self):
        self.check_config_error(
            """
notifications:
- some: thing
sources:
  foo: bar
""",
            '''\
at ['sources'], expected a list:
notifications:
- some: thing
sources:
  foo: bar
''')

    def test_invalid_source(self):
        # not a mapping
        self.check_config_error(
            """
notifications:
- some: thing
sources:
  - []

""",
            '''\
at ['sources', 0], invalid list value:
- []
''')

    def test_multi_line_source_no_type(self):
        self.check_config_error(
            """
sources:
- foo: bar
  baz: bob
notifications:
- email: test@example.com
""",
            '''\
at ['sources', 0], required key not provided, 'type':
baz: bob
foo: bar
''')

    def test_source_repo_not_valid(self):
        # not a mapping
        self.check_config_error(
            """
sources:
- type: bar
  repo: baz
""",
            '''\
source specifies invalid repo 'baz':
name: null
repo: baz
type: bar
''')

    def test_default_repo_not_valid(self):
        # not a mapping
        self.check_config_error(
            """
repos:
  - name: not_config
    type: git
sources:
  - x: y
""",
            '''\
source specifies no repo and the default repo, 'config', is not configured:
name: y
type: x
''')

    def test_duplicate_source_names(self):
        self.check_config_error(
            """
sources:
- type: source_type
  name: thing

- type: source_type
  name: thing
""",
            '''\
more than one source of type 'source_type' named 'thing':
name: thing
repo: config
type: source_type
''')

    def test_duplicate_source_names_but_different_types(self):
        self.check_parses(
            """
sources:
- type: type1
  name: thing

- type: type2
  name: thing
""",
            dict(
                notifications=[default_notifications_config],
                repos=[default_repo_config],
                sources=[
                    dict(type='type1', name='thing', repo='config'),
                    dict(type='type2', name='thing', repo='config'),
                ]
            ))

    def test_duplicate_sources_named_none(self):
        self.check_config_error(
            """
sources:
- type: source_type
  value: thing

- type: source_type
  value: thing
""",
            '''\
more than one source of type 'source_type' named None:
name: null
repo: config
type: source_type
value: thing
''')

    def test_source_list_value(self):
        self.check_parses(
            """
sources:
- paths:
  - /foo
  - /bar
""",
            dict(
                notifications=[default_notifications_config],
                repos=[default_repo_config],
                sources=[
                    dict(type='paths', name=None, repo='config',
                         values=['/foo', '/bar']),
                ]
            ))

    def test_invalid_notifications(self):
        # not list
        self.check_config_error(
            """
sources:
- some: thing
notifications:
  foo: bar
""",
            '''\
at ['notifications'], expected a list:
notifications:
  foo: bar
sources:
- some: thing
''')

    def test_invalid_notification(self):
        # not a mapping
        self.check_config_error(
            """
sources:
- some: thing
notifications:
  -
    - x
    - y
""",
            '''\
at ['notifications', 0], invalid list value:
- - x
  - y
''')

    def test_default_notifications(self):
        self.check_parses(
            """
sources:
- some: thing
""",
            dict(
                notifications=[default_notifications_config],
                repos=[default_repo_config],
                sources=[
                    dict(type='some', name='thing', repo='config')
                ]
            ))


class TestRealise(TestCase):

    def check_config_error(self, config, plugins, expected):
        with ShouldRaise(ConfigError) as s:
            Config.realise(config, plugins)
        compare(expected, str(s.raised), trailing_whitespace=False)

    def test_not_found(self):
        self.check_config_error(
            config=dict(repos=[dict(type='foo')]),
            plugins=Plugins(),
            expected="""\
No plugin found for repo of type 'foo':
type: foo
"""
        )

    def test_no_schema(self):
        class DummyPlugin(Repo): pass
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        with ShouldRaise (
                TypeError("'abstractproperty' object is not callable")
        ):
            Config.realise(dict(repos=[dict(type='foo')]),
                           plugins)

    def test_invalid_config_data(self):
        class DummyPlugin(Repo):
            schema = Schema({Required('type'): str, Required('foo'): int})
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        self.check_config_error(
            config=dict(repos=[dict(type='foo', foo='bar')]),
            plugins=plugins,
            expected="""\
at ['repos', 0, 'foo'], expected int:
foo: bar
type: foo
"""
        )

    def test_plugin_instantiation_exception(self):
        class DummyPlugin(Repo):
            schema = Schema({}, extra=ALLOW_EXTRA)
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        with ShouldRaise (TypeError(
                "Can't instantiate abstract class DummyPlugin "
                "with abstract methods __init__, actions, path_for"
        )):
            Config.realise(dict(repos=[dict(type='foo')]),
                           plugins)

    def test_missing_required_key(self):
        class DummyPlugin(Repo):
            schema = Schema({Required('type'): str, Required('foo'): int})
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        self.check_config_error(
            config=dict(repos=[dict(type='foo')]),
            plugins=plugins,
            expected="""\
at ['repos', 0], required key not provided, 'foo':
type: foo
"""
        )

    def test_plugin_instantiation_exception(self):
        class DummyPlugin(Repo):
            schema = Schema({}, extra=ALLOW_EXTRA)
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        with ShouldRaise (TypeError(
                "Can't instantiate abstract class DummyPlugin "
                "with abstract methods __init__, actions, path_for"
        )):
            Config.realise(dict(repos=[dict(type='foo')]),
                           plugins)

    def test_wrong_type(self):
        class DummyPlugin(object):
            schema = Schema({}, extra=ALLOW_EXTRA)
        plugins = Plugins()
        plugins.register('repo', 'foo', DummyPlugin)
        with ShouldRaise (TypeError):
            Config.realise(dict(repos=[dict(type='foo')]),
                           plugins)

    def test_valid(self):
        # one of each
        class DummyRepo(Repo):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name, x):
                super(DummyRepo, self).__init__(type, name)
                self.x = x
            def actions(self):
                pass
            def path_for(self, source):
                pass

        class DummySource(Source):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name, repo, y):
                super(DummySource, self).__init__(type, name, repo)
                self.y = y
            def process(self, path):
                pass

        class DummyNotifier(Notifier):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name, z):
                super(DummyNotifier, self).__init__(type, name)
                self.z = z
            def start(self):
                pass
            def finish(self):
                pass

        plugins = Plugins()
        plugins.register('repo', 'foo', DummyRepo)
        plugins.register('source', 'bar', DummySource)
        plugins.register('notification', 'baz', DummyNotifier)

        config = Config.realise(dict(repos=[dict(type='foo', name='po', x=1)],
                                     sources=[dict(type='bar', y=2, repo='po',
                                                   name=None)],
                                     notifications=[dict(type='baz', z=3,
                                                         name=None)]),
                                plugins)

        compare({'po': C(DummyRepo, type='foo', name='po', x=1)},
                config.repos)
        compare([C(DummySource, y=2, type='bar', repo='po', name=None)],
                config.sources)
        compare([C(DummyNotifier, z=3, type='baz', name=None)],
                config.notifications)


class TestLoad(WithTempDir, TestCase):

    def test_full_instantiation(self):
        # one of each
        class DummyGit(Repo):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name):
                super(DummyGit, self).__init__(type, name)
            def actions(self):
                pass
            def path_for(self, source):
                pass

        class DummyPath(Source):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name, repo):
                super(DummyPath, self).__init__(type, name, repo)
            def process(self, path):
                pass

        class DummyEmail(Notifier):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, name):
                super(DummyEmail, self).__init__(type, name)
            def start(self):
                pass
            def finish(self):
                pass

        plugins = Plugins()
        plugins.register('repo', 'git', DummyGit)
        plugins.register('source', 'path', DummyPath)
        plugins.register('notification', 'email', DummyEmail)

        source = open(self.dir.write('test.yaml', """
repos:
  - name: config
    type: git

sources:
- path: /some/path

notifications:
- email: test@example.com
"""))
        config = Config.load(source, plugins)
        compare(
            C(Config,
              repos=dict(config=C(DummyGit, type='git', name='config')),
              sources=[C(DummyPath,
                         type='path', repo='config', name='/some/path')],
              notifications=[
                  C(DummyEmail, type='email', name='test@example.com')
              ]),
            config
        )
