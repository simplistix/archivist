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


class TestParse(TestCase):

    def setUp(self):
        self.dir = TempDirectory()

    def tearDown(self):
        self.dir.cleanup()

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
                dict(type='path', value='/some/path', repo='config'),
                dict(type='crontab', value='root', repo='config'),
                dict(type='jenkins', username='foo', password='bar',
                     repo='config'),
            ],
            notifications=[
                dict(type='email', value='test@example.com')
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
name: config
type: git
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
- foo
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
                    dict(type='some', value='thing')
                ],
                repos=[default_repo_config],
                sources=[
                    dict(type='some', value='thing', repo='config')
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
[]
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
[]
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
type: x
value: y
''')

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
foo: bar
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
- x
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
                    dict(type='some', value='thing', repo='config')
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
at ['foo'], expected int:
bar
...
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
            def __init__(self, type, repo, y):
                super(DummySource, self).__init__(type, repo)
                self.y = y
            def process(self, path):
                pass

        class DummyNotifier(Notifier):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, type, z):
                super(DummyNotifier, self).__init__(type)
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
                                     sources=[dict(type='bar', y=2, repo='po')],
                                     notifications=[dict(type='baz', z=3)]),
                                plugins)

        compare({'po': C(DummyRepo, type='foo', name='po', x=1)},
                config.repos)
        compare([C(DummySource, y=2, type='bar', repo='po')],
                config.sources)
        compare([C(DummyNotifier, z=3, type='baz')],
                config.notifications)
