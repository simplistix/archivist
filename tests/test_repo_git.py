import os
from unittest import TestCase
from testfixtures import TempDirectory, compare, LogCapture, test_datetime, \
    Replacer
from voluptuous import Schema
from archivist.config import default_repo_config
from archivist.helpers import run
from archivist.plugins import Source
from archivist.repos.git import Plugin as GitRepo


def make_git_repo(**params):
    params.update(type='git', name='test')
    return GitRepo(**GitRepo.schema(params))


class PluginTests(TestCase):

    def test_schema_defaults(self):
        compare(dict(type='git', name='config', path='/foo',
                     git='git', commit=True, push=False),
                GitRepo.schema(dict(type='git', path='/foo', name='config')))

    def test_schema_everything(self):
        compare(dict(type='git', name='config', path='/foo',
                     git='svn', commit=False, push=True),
                GitRepo.schema(dict(type='git', name='config', path='/foo',
                                    git='svn', commit=False, push=True)))


class PluginWithTempDirTests(TestCase):

    def setUp(self):
        self.dir = TempDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_actions(self, path=None, **kw):
        with LogCapture() as log:
            plugin = make_git_repo(path=path or self.dir.path, **kw)
            with Replacer() as r:
                r.replace('archivist.repos.git.datetime', test_datetime())
                plugin.actions()
        return log

    def git(self, command, repo_path=None):
        return run(['git'] + command.split(), cwd=repo_path or self.dir.path)

    def make_repo_with_content(self, repo=''):
        repo_path = self.dir.getpath(repo) if repo else None
        self.git('init', repo_path)
        self.dir.write(repo + 'a', 'some content')
        self.dir.write(repo + 'b', 'other content')
        self.dir.write(repo + 'c', 'more content')
        self.git('add .', repo_path)
        self.git('commit -m initial', repo_path)
        return repo

    def make_local_changes(self, repo=''):
        self.dir.write(repo + 'b', 'changed content')
        os.remove(self.dir.getpath(repo + 'c'))
        self.dir.write(repo + 'd', 'new content')

    def status_log_entry(self, lines, repo_path=None):
        return ('archivist.repos.git', 'INFO',
                '\n'.join(l.format(repo=repo_path or self.dir.path)
                          for l in lines)+'\n')

    def check_git_log(self, lines, repo_path=None):
        compare('\n'.join(lines)+'\n',
                self.git('log --pretty=format:%s --stat', repo_path))

    def get_dummy_source(self, name):
        class DummySource(Source):
            schema = Schema({})
            def __init__(self, type, name, repo):
                super(DummySource, self).__init__(type, name, repo)
            def process(self, path):
                pass
        return DummySource('dummy', name, 'repo')

    def test_path_for_with_name(self):
        compare(self.dir.getpath('dummy/the_name'),
                make_git_repo(path=self.dir.path).path_for(
                    self.get_dummy_source('the_name')
                ))
        self.assertTrue(os.path.exists(self.dir.getpath('dummy/the_name')))

    def test_path_for_no_name(self):
        compare(self.dir.getpath('dummy'),
                make_git_repo(path=self.dir.path).path_for(
                    self.get_dummy_source(name=None)
                ))
        self.assertTrue(os.path.exists(self.dir.getpath('dummy')))

    def test_not_there(self):
        repo_path = self.dir.getpath('var')
        log = self.run_actions(repo_path)
        log.check(
            ('archivist.repos.git', 'INFO', 'creating git repo at '+repo_path)
        )
        self.assertTrue(self.dir.getpath('var/.git'))

    def test_there_not_git(self):
        repo_path = self.dir.makedir('var')
        log = self.run_actions(repo_path)
        log.check(
            ('archivist.repos.git', 'INFO',
             'creating git repo at '+repo_path)
        )
        self.assertTrue(self.dir.getpath('var/.git'))

    def test_no_changes(self):
        self.git('init')
        log = self.run_actions()
        log.check() # no logging

    def test_just_log_changes(self):
        self.make_repo_with_content()
        self.make_local_changes()
        log = self.run_actions(commit=False)
        log.check(self.status_log_entry([
            'changes found in git repo at {repo}:',
            ' M b',
            ' D c',
            '?? d',
        ]))
        self.check_git_log([
            'initial',
            ' a | 1 +',
            ' b | 1 +',
            ' c | 1 +',
            ' 3 files changed, 3 insertions(+)',
        ])

    def test_commit_changes(self):
        self.make_repo_with_content()
        self.make_local_changes()
        log = self.run_actions(commit=True)
        log.check(self.status_log_entry([
            'changes found in git repo at {repo}:',
            ' M b',
            ' D c',
            '?? d',
            ]),
            ('archivist.repos.git', 'INFO', 'changes committed'),
            )
        compare('', self.git('status --porcelain'))
        self.check_git_log([
            'Recorded by archivist at 2001-01-01 00:00',
            ' b | 2 +-',
            ' c | 1 -',
            ' d | 1 +',
            ' 3 files changed, 2 insertions(+), 2 deletions(-)',
            '',
            'initial',
            ' a | 1 +',
            ' b | 1 +',
            ' c | 1 +',
            ' 3 files changed, 3 insertions(+)',
        ])

    def test_push_changes(self):
        origin_path = self.dir.makedir('origin')
        self.make_repo_with_content(repo='origin/')
        self.git("config --local --add receive.denyCurrentBranch ignore",
                 origin_path)
        self.git('clone -q ' + origin_path + ' local')
        self.make_local_changes(repo='local/')

        local_path = self.dir.getpath('local')
        log = self.run_actions(commit=True, push=True, path=local_path)
        log.check(self.status_log_entry([
            'changes found in git repo at {repo}:',
            ' M b',
            ' D c',
            '?? d',
            ], repo_path=local_path),
            ('archivist.repos.git', 'INFO', 'changes committed'),
            ('archivist.repos.git', 'INFO', 'changes pushed'),
            )
        self.check_git_log([
            'Recorded by archivist at 2001-01-01 00:00',
            ' b | 2 +-',
            ' c | 1 -',
            ' d | 1 +',
            ' 3 files changed, 2 insertions(+), 2 deletions(-)',
            '',
            'initial',
            ' a | 1 +',
            ' b | 1 +',
            ' c | 1 +',
            ' 3 files changed, 3 insertions(+)'],
            repo_path=origin_path
        )

    def test_default_repo_config(self):
        # can't test actions due to default path
        GitRepo(**GitRepo.schema(default_repo_config))


