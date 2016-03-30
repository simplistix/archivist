from email import message_from_string
from logging import getLogger
from unittest import TestCase

from mock import patch, call
from testfixtures import Comparison as C, LogCapture, compare

from archivist.notifications.email import Plugin
from tests.helpers import ShouldFailSchemaWith

logger = getLogger()

class PluginTests(TestCase):

    def test_bad_log_level(self):
        text = "no log level named 'wrong' for dictionary value @ data['level']"
        with ShouldFailSchemaWith(text):
            Plugin.schema(dict(level='wrong'))

    def full_cycle(self, **kw):
        params = dict(type='email', name=None)
        params.update(kw)
        with LogCapture():
            with patch('smtplib.SMTP', autospec=True) as smtp:
                plugin = Plugin(**Plugin.schema(params))
                logger.info('before')
                plugin.start()
                logger.debug('during-debug')
                logger.info('during-info')
                logger.warn('during-warning')
                logger.error('during-error')
                plugin.finish()
                logger.info('after')
        return smtp

    def test_minimal(self):
        smtp = self.full_cycle(recipient='to@example.com')
        compare([
            call('localhost', 25),
            call().sendmail('to@example.com', ['to@example.com'],
                            C(str)),
            call().quit()
        ], smtp.mock_calls)

        message = message_from_string(smtp.mock_calls[1][1][2])

        compare(message['subject'], 'Archivist Notification (ERROR)')
        compare(message.get_payload(decode=True),
                'during-info\n'
                'during-warning\n'
                'during-error\n')

    def test_maximal(self):
        smtp = self.full_cycle(level='WARNING',
                               fmt='%(asctime)s %(levelname)s %(message)s',
                               datefmt='foo',
                               sender='from@example.com',
                               recipient='to@example.com',
                               mailhost='mh',
                               username='u',
                               password='p',
                               headers={'x-foo': 'bar baz'})
        compare([
            call('mh', 25),
            call().login('u', 'p'),
            call().sendmail('from@example.com', ['to@example.com'],
                            C(str)),
            call().quit()
        ], smtp.mock_calls)

        message = message_from_string(smtp.mock_calls[2][1][2])

        compare(message['subject'], 'Archivist Notification (ERROR)')
        compare(message['x-foo'], 'bar baz')
        compare(message.get_payload(decode=True),
                'foo WARNING during-warning\n'
                'foo ERROR during-error\n')

    def test_send_level_prevent(self):
        smtp = self.full_cycle(send_level='CRITICAL',
                               recipient='to@example.com')
        compare([], smtp.mock_calls)

    def test_send_level_allow(self):
        smtp = self.full_cycle(level='ERROR',
                               send_level='ERROR',
                               recipient='to@example.com')
        message = message_from_string(smtp.mock_calls[1][1][2])

        compare(message['subject'], 'Archivist Notification (ERROR)')
        compare(message.get_payload(decode=True),
                'during-error\n')
