from unittest import TestCase
from testfixtures import TempDirectory, compare, ShouldRaise
from archivist.config import Config, ConfigError, default_repo_config, \
    default_notifications_config


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
                dict(type='path', value='/some/path'),
                dict(type='crontab', value='root'),
                dict(type='jenkins', username='foo', password='bar'),
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
                    dict(type='some', value='thing')
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
                    dict(type='some', value='thing')
                ]
            ))
