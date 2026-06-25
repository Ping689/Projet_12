import unittest
from unittest.mock import patch

import scripts.notify_pipeline as notify_pipeline


class SlackNotificationTest(unittest.TestCase):
    @patch("scripts.notify_pipeline.requests.post")
    @patch("scripts.notify_pipeline.os.environ", {"SLACK_WEBHOOK_URL": "https://example.test/webhook"})
    def test_notify_slack_posts_summary_message(self, post):
        post.return_value.raise_for_status.return_value = None

        notify_pipeline.main()

        post.assert_called_once()
        self.assertIn("text", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()
