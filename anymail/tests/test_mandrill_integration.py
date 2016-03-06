from __future__ import unicode_literals

import os
import unittest

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings

from anymail.exceptions import AnymailAPIError, AnymailRecipientsRefused


MANDRILL_TEST_API_KEY = os.getenv('MANDRILL_TEST_API_KEY')


@unittest.skipUnless(MANDRILL_TEST_API_KEY,
            "Set MANDRILL_TEST_API_KEY environment variable to run integration tests")
@override_settings(MANDRILL_API_KEY=MANDRILL_TEST_API_KEY,
                   EMAIL_BACKEND="anymail.backends.mandrill.MandrillBackend")
class DjrillIntegrationTests(TestCase):
    """Mandrill API integration tests

    These tests run against the **live** Mandrill API, using the
    environment variable `MANDRILL_TEST_API_KEY` as the API key.
    If that variable is not set, these tests won't run.

    See https://mandrill.zendesk.com/hc/en-us/articles/205582447
    for info on Mandrill test keys.

    """

    def setUp(self):
        self.message = mail.EmailMultiAlternatives(
            'Subject', 'Text content', 'from@example.com', ['to@example.com'])
        self.message.attach_alternative('<p>HTML content</p>', "text/html")

    def test_send_mail(self):
        # Example of getting the Mandrill send status and _id from the message
        sent_count = self.message.send()
        self.assertEqual(sent_count, 1)

        # noinspection PyUnresolvedReferences
        anymail_status = self.message.anymail_status
        sent_status = anymail_status.recipients['to@example.com'].status
        message_id = anymail_status.recipients['to@example.com'].message_id

        self.assertIn(sent_status, ['sent', 'queued'])  # successful send (could still bounce later)
        self.assertGreater(len(message_id), 0)  # don't know what it'll be, but it should exist

        self.assertEqual(anymail_status.status, {sent_status})  # set of all recipient statuses
        self.assertEqual(anymail_status.message_id, message_id)  # because only a single recipient (else would be a set)

    def test_invalid_from(self):
        # Example of trying to send from an invalid address
        # Mandrill returns a 500 response (which raises a MandrillAPIError)
        self.message.from_email = 'webmaster@localhost'  # Django default DEFAULT_FROM_EMAIL
        try:
            self.message.send()
            self.fail("This line will not be reached, because send() raised an exception")
        except AnymailAPIError as err:
            self.assertEqual(err.status_code, 500)
            self.assertIn("email address is invalid", str(err))

    def test_invalid_to(self):
        # Example of detecting when a recipient is not a valid email address
        self.message.to = ['invalid@localhost']
        try:
            self.message.send()
        except AnymailRecipientsRefused:
            # Mandrill refused to deliver the mail -- message.anymail_status will tell you why:
            # noinspection PyUnresolvedReferences
            anymail_status = self.message.anymail_status
            self.assertEqual(anymail_status.recipients['invalid@localhost'].status, 'invalid')
            self.assertEqual(anymail_status.status, {'invalid'})
        else:
            # Sometimes Mandrill queues these test sends
            # noinspection PyUnresolvedReferences
            if self.message.anymail_status.status == {'queued'}:
                self.skipTest("Mandrill queued the send -- can't complete this test")
            else:
                self.fail("Djrill did not raise AnymailRecipientsRefused for invalid recipient")

    def test_rejected_to(self):
        # Example of detecting when a recipient is on Mandrill's rejection blacklist
        self.message.to = ['reject@test.mandrillapp.com']
        try:
            self.message.send()
        except AnymailRecipientsRefused:
            # Mandrill refused to deliver the mail -- message.anymail_status will tell you why:
            # noinspection PyUnresolvedReferences
            anymail_status = self.message.anymail_status
            self.assertEqual(anymail_status.recipients['reject@test.mandrillapp.com'].status, 'rejected')
            self.assertEqual(anymail_status.status, {'rejected'})
        else:
            # Sometimes Mandrill queues these test sends
            # noinspection PyUnresolvedReferences
            if self.message.anymail_status.status == {'queued'}:
                self.skipTest("Mandrill queued the send -- can't complete this test")
            else:
                self.fail("Djrill did not raise AnymailRecipientsRefused for blacklist recipient")

    @override_settings(MANDRILL_API_KEY="Hey, that's not an API key!")
    def test_invalid_api_key(self):
        # Example of trying to send with an invalid MANDRILL_API_KEY
        try:
            self.message.send()
            self.fail("This line will not be reached, because send() raised an exception")
        except AnymailAPIError as err:
            self.assertEqual(err.status_code, 500)
            self.assertIn("Invalid API key", str(err))
