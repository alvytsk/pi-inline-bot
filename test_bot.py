import io
import json
import unittest
from unittest import mock

import bot


class ParseAllowedTest(unittest.TestCase):
    def test_parses_comma_and_space_separated_ids(self):
        self.assertEqual(bot.parse_allowed("123, 456 789"), {123, 456, 789})

    def test_empty_means_nobody(self):
        self.assertEqual(bot.parse_allowed(""), set())


class InlineResultTest(unittest.TestCase):
    def test_result_has_placeholder_and_button(self):
        r = bot.inline_result("what is uptime?")
        self.assertEqual(r["type"], "article")
        self.assertEqual(r["title"], "Ask pi")
        self.assertLessEqual(len(r["id"].encode()), 64)
        self.assertIn("what is uptime?", r["input_message_content"]["message_text"])
        self.assertEqual(r["input_message_content"]["message_text"],
                         "💬 what is uptime?\n\n🤖 thinking…")
        # Without an inline keyboard Telegram does not send inline_message_id.
        self.assertTrue(r["reply_markup"]["inline_keyboard"][0])
        self.assertEqual(r["reply_markup"]["inline_keyboard"][0][0]["text"], "🤖 pi is thinking…")

    def test_assistant_name_is_used_in_title_and_button(self):
        r = bot.inline_result("q", name="Jeeves")
        self.assertEqual(r["title"], "Ask Jeeves")
        self.assertEqual(r["reply_markup"]["inline_keyboard"][0][0]["text"], "🤖 Jeeves is thinking…")

    def test_same_query_gives_same_id(self):
        self.assertEqual(bot.inline_result("a")["id"], bot.inline_result("a")["id"])


class FormatAnswerTest(unittest.TestCase):
    def test_contains_question_and_answer(self):
        text = bot.format_answer("q?", "the answer")
        self.assertEqual(text, "💬 q?\n\n🤖 the answer")

    def test_truncates_to_telegram_limit(self):
        text = bot.format_answer("q", "x" * 10000)
        self.assertLessEqual(len(text), bot.MAX_TEXT)
        self.assertTrue(text.endswith("…"))

    def test_empty_answer_is_marked(self):
        self.assertIn("empty", bot.format_answer("q", "   "))


class RunPiErrorTest(unittest.TestCase):
    def test_timeout_is_reported_with_error_icon(self):
        b = bot.Bot("T", set(), "pi", [], 3, "/", 1)
        with mock.patch("subprocess.run", side_effect=bot.subprocess.TimeoutExpired("pi", 3)):
            self.assertEqual(b.run_pi("q"), "⛔ pi timed out after 3s")


class PiCommandTest(unittest.TestCase):
    def test_query_goes_after_double_dash(self):
        cmd = bot.pi_command("pi", ["-p", "--no-session"], "--help me")
        self.assertEqual(cmd[-2:], ["--", "--help me"])
        self.assertEqual(cmd[0], "pi")


class PollTest(unittest.TestCase):
    def test_long_poll_sends_timeout_to_api_and_waits_longer_over_http(self):
        b = bot.Bot("T", set(), "pi", [], 1, "/", 1)
        resp = io.BytesIO(b'{"ok": true, "result": []}')
        with mock.patch("urllib.request.urlopen", return_value=resp) as urlopen:
            self.assertEqual(b.poll(7), [])
        req = urlopen.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(body["offset"], 7)
        self.assertEqual(body["timeout"], 50)
        self.assertGreater(urlopen.call_args.kwargs["timeout"], body["timeout"])


if __name__ == "__main__":
    unittest.main()
