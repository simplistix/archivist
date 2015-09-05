from argparse import ArgumentParser, FileType
import logging

from .config import Config, ConfigError, default_repo_config
from .plugins import Plugins

logger = logging.getLogger(__name__)

def parse_command_line():
    parser = ArgumentParser()
    parser.add_argument('config',
                        help='Absolute path to the yaml config file',
                        default=default_repo_config['path'] + '/config.yaml',
                        type=FileType('r'),
                        nargs='?')
    args = parser.parse_args()
    return args


class HandleKnownExceptions(object):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ConfigError:
            print('{}: {}'.format(exc_type.__name__, exc_val))
            raise SystemExit(1)


class SafeNotifications(object):

    def __init__(self, notifiers):
        self.notifiers = notifiers
        self.active = []

    def __enter__(self):

        for notifier in self.notifiers:
            try:
                notifier.start()
            except:
                if self.active:
                    logger.exception('error starting %r', notifier.name)
                else:
                    raise
            self.active.append(notifier)

    def __exit__(self, exc_type, exc_val, exc_tb):

        if exc_type:
            logger.exception('unexpected error:')

        while self.active:
            notifier = self.active.pop()
            try:
                notifier.finish()
            except:
                if self.active:
                    logger.exception('error stoping %r', notifier.name)
                else:
                    raise

        return True


def main():

    plugins = Plugins.load()

    args = parse_command_line()

    with HandleKnownExceptions():

        config = Config.load(args.config, plugins)

        with SafeNotifications(config.notifications):

            for source in config.sources:
                repo = config.repo_for(source)
                path = repo.path_for(source)
                source.process(path)

            for repo in config.repos.values():
                repo.actions()
