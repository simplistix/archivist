from logging import getLogger
import os
from datetime import datetime
from voluptuous import Schema, Required
from archivist.helpers import run, ensure_dir_exists
from archivist.plugins import Repo


logger = getLogger(__name__)

class Plugin(Repo):

    schema = Schema({
        'type': 'git',
        Required('name'): str,
        Required('path'): str,
        Required('git', default='git'): str,
        Required('commit', default=True): bool,
        Required('push', default=False): bool,
    })

    def __init__(self, type, name, path, git, commit, push):
        super(Plugin, self).__init__(type, name)
        self.path = path
        self.git = git
        self.commit = commit
        self.push = push

    def path_for(self, source):
        """
        :param source: a :class:`Source` instance.

        :return: An absolute path to a directory where sources can write.
                 This does not need to be empty and may be temporary.
        """
        parts = [self.path, source.type]
        if source.name:
            parts.append(source.name)
        full_path = os.path.join(*parts)
        ensure_dir_exists(full_path)
        return full_path

    def run_git(self, *args):
        return run((self.git, )+args, cwd=self.path)

    def actions(self):
        # git init if required
        ensure_dir_exists(self.path)
        if not os.path.exists(os.path.join(self.path, '.git')):
            logger.info('creating git repo at %s', self.path)
            self.run_git('init')

        # log status
        status = self.run_git('status', '--porcelain')
        if status:
            logger.info('changes found in git repo at %s:\n%s',
                        self.path, status)

        # commit if specified
        if self.commit and status:
            self.run_git('add', '.')
            self.run_git('commit', '-m',
                         datetime.now().strftime(
                             "Recorded by archivist at %Y-%m-%d %H:%M"
                         ))
            logger.info('changes committed')

        # push if specified
        if self.push:
            self.run_git('push', '-q')
            logger.info('changes pushed')

