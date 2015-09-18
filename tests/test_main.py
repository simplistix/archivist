from logging import getLogger
from unittest import TestCase

from mock import Mock, call
from testfixtures import (
    Replacer, tempdir, compare, ShouldRaise, OutputCapture, TempDirectory,
    LogCapture
)
from voluptuous import Schema
from voluptuous import ALLOW_EXTRA

from archivist.config import ConfigError
from archivist.main import (
    parse_command_line, HandleKnownExceptions, main, SafeNotifications
)
from archivist.plugins import Repo, Source, Notifier


class TestParseCommandLine(TestCase):

    def check(self, argv):
        with Replacer() as r:
            r.replace('sys.argv', ['x']+argv)
            return parse_command_line()

    @tempdir()
    def test_okay(self, dir):
        path = dir.write('test.yaml', 'foo')
        args = self.check([path])
        compare('foo', args.config.read())

    @tempdir()
    def test_not_okay(self, dir):
        path = dir.getpath('bad.yaml')
        with ShouldRaise(SystemExit(2)):
            with OutputCapture() as output:
                self.check([path])
        self.assertTrue("can't open" in output.captured)
        self.assertTrue(path in output.captured)

    @tempdir()
    def test_default(self, dir):
        dir.write('config.yaml', 'foo')
        with Replacer() as r:
            r.replace('archivist.config.default_repo_config.path', dir.path)
            args = self.check([])
        compare('foo', args.config.read())


class TestHandleKnownExceptions(TestCase):

    def test_config_error(self):
        with ShouldRaise(SystemExit(1)):
            with OutputCapture() as output:
                with HandleKnownExceptions():
                    raise ConfigError('foo', dict(x=1, y=2))
        # when the exception isn't caught, nothing should be printed
        output.compare('ConfigError: foo: \n'
                       'x: 1\n'
                       'y: 2\n')

    def test_value_error(self):
        with ShouldRaise(ValueError('foo')):
            with OutputCapture() as output:
                with HandleKnownExceptions():
                    raise ValueError('foo')
        # when the exception isn't caught, nothing should be printed
        output.compare('')


class DummyNotifier(object):

    def __init__(self, name, logger, bad_start=False, bad_finish=False):
        self.name = name
        self.logger = logger
        self.bad_start = bad_start
        self.bad_finish = bad_finish

    def start(self):
        if self.bad_start:
            raise Exception('start-'+self.name)
        self.logger.info('start-'+self.name)

    def finish(self):
        if self.bad_finish:
            raise Exception('finish-'+self.name)
        self.logger.info('finish-'+self.name)


class TestSafeNotifications(TestCase):

    def setUp(self):
        self.capture = LogCapture()
        self.addCleanup(self.capture.uninstall)
        self.logger = getLogger()

    def test_okay(self):
        with SafeNotifications([
            DummyNotifier('one', self.logger),
            DummyNotifier('two', self.logger),
        ]):
            self.logger.info('payload')

        self.capture.check(
            ('root', 'INFO', 'start-one'),
            ('root', 'INFO', 'start-two'),
            ('root', 'INFO', 'payload'),
            ('root', 'INFO', 'finish-two'),
            ('root', 'INFO', 'finish-one'),
        )

    def test_exception(self):
        with SafeNotifications([DummyNotifier('one', self.logger)]):
            raise Exception('Boom!')

        self.capture.check(
            ('root', 'INFO', 'start-one'),
            ('archivist.main', 'ERROR', 'unexpected error:'),
            ('root', 'INFO', 'finish-one'),
        )

    def test_notification_start_fail(self):
        with SafeNotifications([
            DummyNotifier('one', self.logger),
            DummyNotifier('two', self.logger, bad_start=True),
        ]):
            self.logger.info('payload')

    def test_notification_finish_failed(self):
        with SafeNotifications([
            DummyNotifier('one', self.logger),
            DummyNotifier('two', self.logger, bad_finish=True),
        ]):
            self.logger.info('payload')

    def test_notification_start_none_setup(self):
        with ShouldRaise(Exception('start-one')):
            with SafeNotifications([
                DummyNotifier('one', self.logger, bad_start=True)
            ]):
                self.logger.info('payload')

        self.capture.check() # no logging!

    def test_notification_start_none_finished(self):
        with ShouldRaise(Exception('finish-one')):
            with SafeNotifications([
                DummyNotifier('one', self.logger, bad_finish=True)
            ]):
                self.logger.info('payload')

        self.capture.check(
            ('root', 'INFO', 'start-one'),
            ('root', 'INFO', 'payload'),
        )



class TestMain(TestCase):

    def test_full_sweep(self):
        m = Mock()

        class MockPluginInit(object):
            schema = Schema({}, extra=ALLOW_EXTRA)
            def __init__(self, **kw):
                getattr(m, self.__class__.__name__)(**kw)
                super(MockPluginInit, self).__init__(**kw)

        class TestRepo(MockPluginInit, Repo):
            def actions(self):
                getattr(m.TestRepo, self.name).actions()
            def path_for(self, source):
                source_type = source.__class__.__name__
                getattr(m.TestRepo, self.name).path_for(source_type)
                return '/tmp/' + self.name + '/' + source_type

        class TestS1(MockPluginInit, Source):
            def process(self, path):
                getattr(m, self.__class__.__name__).process(path)
        class TestS2(TestS1):
            pass

        class TestNotifier(MockPluginInit, Notifier):
            def start(self):
                m.TestNotifier.start(self.name)
            def finish(self):
                m.TestNotifier.finish(self.name)

        def load_plugins(cls):
            registry = cls()
            registry.register('repo', 'test', TestRepo)
            registry.register('source', 'test1', TestS1)
            registry.register('source', 'test2', TestS2)
            registry.register('notification', 'test', TestNotifier)
            return registry

        with TempDirectory() as dir:
            path = dir.write('test.yaml', '''
repos:
  - name: r1
    type: test
  - name: r2
    type: test

sources:
- type: test1
  repo: r1
- type: test2
  repo: r2

notifications:
- type: test
  name: t1
  level: 0
  fmt: f
  datefmt: d
- type: test
  name: t2
  level: 0
  fmt: f
  datefmt: d
''')
            with Replacer() as r:
                r.replace('sys.argv', ['x', path])
                r.replace('archivist.plugins.Plugins.load', load_plugins)
                main()

        compare([
            call.TestRepo(type='test', name='r1'),
            call.TestRepo(type='test', name='r2'),
            call.TestS1(repo='r1', type='test1', name=None),
            call.TestS2(repo='r2', type='test2', name=None),
            call.TestNotifier(type='test', name='t1',
                              fmt='f', datefmt='d', level=0),
            call.TestNotifier(type='test', name='t2',
                              fmt='f', datefmt='d', level=0),
            call.TestNotifier.start('t1'),
            call.TestNotifier.start('t2'),
            call.TestRepo.r1.path_for('TestS1'),
            call.TestS1.process('/tmp/r1/TestS1'),
            call.TestRepo.r2.path_for('TestS2'),
            call.TestS2.process('/tmp/r2/TestS2'),
            call.TestRepo.r1.actions(),
            call.TestRepo.r2.actions(),
            # finish in reverse in case anyone wants to do transaction-y
            # things
            call.TestNotifier.finish('t2'),
            call.TestNotifier.finish('t1'),
        ], m.mock_calls)

