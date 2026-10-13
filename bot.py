#!/usr/bin/env python3
"""Telegram inline bot: type `@bot question`, pi answers in the same message.

Flow: inline_query -> one article with a "thinking" placeholder and a button
(the button is required, otherwise Telegram omits inline_message_id) ->
chosen_inline_result (needs /setinlinefeedback) -> run `pi -p` -> editMessageText.
"""
import hashlib
import json
import logging
import os
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request

MAX_TEXT = 4096  # Telegram message length limit
Q_ICON = "💬"
PI_ICON = "🤖"
ERR_ICON = "⛔"
DEFAULT_PI_ARGS = (
    "-p --no-session --tools read,grep,find,ls "
    "--append-system-prompt 'Your reply is shown in a Telegram message: "
    "be concise, use plain text without Markdown.'"
)

log = logging.getLogger("pi-inline-bot")


def parse_allowed(raw):
    return {int(x) for x in raw.replace(",", " ").split()}


def inline_result(query, name="pi"):
    return {
        "type": "article",
        "id": hashlib.sha1(query.encode()).hexdigest(),
        "title": f"Ask {name}",
        "description": query,
        "input_message_content": {"message_text": f"{Q_ICON} {query}\n\n{PI_ICON} thinking…"},
        "reply_markup": {
            "inline_keyboard": [[{"text": f"{PI_ICON} {name} is thinking…", "callback_data": "wait"}]]
        },
    }


def format_answer(query, answer):
    answer = answer.strip() or "(pi returned an empty answer)"
    text = f"{Q_ICON} {query}\n\n{PI_ICON} {answer}"
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    return text


def pi_command(pi_bin, pi_args, query):
    return [pi_bin, *pi_args, "--", query]


class Bot:
    def __init__(self, token, allowed, pi_bin, pi_args, pi_timeout, pi_cwd, max_jobs, name="pi"):
        self.api = f"https://api.telegram.org/bot{token}/"
        self.name = name
        self.allowed = allowed
        self.pi_bin = pi_bin
        self.pi_args = pi_args
        self.pi_timeout = pi_timeout
        self.pi_cwd = pi_cwd
        self.jobs = threading.Semaphore(max_jobs)

    def call(self, method, http_timeout=10, **params):
        req = urllib.request.Request(
            self.api + method,
            data=json.dumps(params).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=http_timeout) as resp:
                return json.load(resp)["result"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method}: {e.code} {e.read().decode(errors='replace')}") from e

    def on_inline_query(self, q):
        user = q["from"]
        query = q["query"].strip()
        if user["id"] not in self.allowed:
            log.warning("rejected inline query from user id=%s (@%s)", user["id"], user.get("username"))
            results = []
        else:
            results = [inline_result(query, self.name)] if query else []
        self.call("answerInlineQuery", inline_query_id=q["id"], results=results,
                  cache_time=0, is_personal=True)

    def on_chosen(self, r):
        if r["from"]["id"] not in self.allowed or "inline_message_id" not in r:
            return
        threading.Thread(target=self.answer, args=(r["inline_message_id"], r["query"].strip()),
                         daemon=True).start()

    def answer(self, message_id, query):
        with self.jobs:
            log.info("asking pi: %r", query)
            text = format_answer(query, self.run_pi(query))
        try:
            self.call("editMessageText", inline_message_id=message_id, text=text)
        except Exception:
            log.exception("failed to edit message")

    def run_pi(self, query):
        try:
            p = subprocess.run(pi_command(self.pi_bin, self.pi_args, query), cwd=self.pi_cwd,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=self.pi_timeout)
        except subprocess.TimeoutExpired:
            return f"{ERR_ICON} pi timed out after {self.pi_timeout}s"
        except OSError as e:
            return f"{ERR_ICON} could not start pi: {e}"
        if p.returncode != 0:
            return f"{ERR_ICON} pi failed (exit {p.returncode}):\n{(p.stderr or p.stdout).strip()[-1000:]}"
        return p.stdout

    def on_callback(self, c):
        self.call("answerCallbackQuery", callback_query_id=c["id"], text=f"{self.name} is still thinking…")

    def run(self):
        me = self.call("getMe")
        log.info("running as @%s, allowed users: %s", me["username"], sorted(self.allowed) or "nobody")
        offset = 0
        while True:
            try:
                updates = self.poll(offset)
            except Exception:
                log.exception("getUpdates failed, retrying in 5s")
                time.sleep(5)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                try:
                    if "inline_query" in u:
                        self.on_inline_query(u["inline_query"])
                    elif "chosen_inline_result" in u:
                        self.on_chosen(u["chosen_inline_result"])
                    elif "callback_query" in u:
                        self.on_callback(u["callback_query"])
                except Exception:
                    log.exception("failed to handle update %s", u["update_id"])

    def poll(self, offset):
        params = {"offset": offset, "timeout": 50,
                  "allowed_updates": ["inline_query", "chosen_inline_result", "callback_query"]}
        return self.call("getUpdates", http_timeout=60, **params)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Bot(
        token=os.environ["BOT_TOKEN"],
        allowed=parse_allowed(os.environ.get("ALLOWED_USERS", "")),
        pi_bin=os.environ.get("PI_BIN", "pi"),
        pi_args=shlex.split(os.environ.get("PI_ARGS", DEFAULT_PI_ARGS)),
        pi_timeout=int(os.environ.get("PI_TIMEOUT", "180")),
        pi_cwd=os.environ.get("PI_CWD") or os.path.expanduser("~"),
        max_jobs=int(os.environ.get("PI_MAX_JOBS", "2")),
        name=os.environ.get("ASSISTANT_NAME") or "pi",
    ).run()


if __name__ == "__main__":
    main()
