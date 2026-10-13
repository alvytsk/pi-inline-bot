# pi-inline-bot

A Telegram inline bot that lets you ask [pi](https://github.com/badlogic/pi-mono) from any chat.
Type `@your_bot what is my uptime?`, pick the result, and the message fills in with pi's answer
once it is ready.

```
💬 what is my uptime?

🤖 up 3 days, 4:12
```

Single file, Python standard library only, long polling — no web server or public IP needed.

## How it works

1. `inline_query` → the bot offers one article with a "thinking…" placeholder and a button.
   The button is required: without an inline keyboard Telegram does not send `inline_message_id`.
2. `chosen_inline_result` → the bot runs `pi -p -- "<query>"` in the background.
3. `editMessageText` → the placeholder is replaced with the answer (truncated to 4096 chars).

Only users listed in `ALLOWED_USERS` get a result; everyone else sees nothing and is logged.
By default pi runs with read-only tools (`read,grep,find,ls`) and no session.

## Setup

Requirements: Python 3.10+, and `pi` installed and logged in for the user that runs the bot.

1. Create a bot with [@BotFather](https://t.me/BotFather): `/newbot`, then
   `/setinline` (enable inline mode) and `/setinlinefeedback` → `Enabled`
   (without feedback the bot never learns which result was chosen).
2. Configure:

   ```sh
   git clone https://github.com/alvytsk/pi-inline-bot.git ~/pi-inline-bot
   cd ~/pi-inline-bot
   cp bot.env.example bot.env
   chmod 600 bot.env
   $EDITOR bot.env   # set BOT_TOKEN and ALLOWED_USERS
   ```

   Don't know your Telegram user ID? Leave `ALLOWED_USERS` empty, start the bot, send it an
   inline query, and copy the ID from the `rejected inline query from user id=...` log line.
3. Run it in the foreground to check:

   ```sh
   set -a; . ./bot.env; set +a
   python3 bot.py
   ```

## Running as a service

`pi-inline-bot@.service` is a systemd template; the instance name is the user to run as,
and the checkout is expected at `/home/<user>/pi-inline-bot`.

```sh
sudo cp pi-inline-bot@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-inline-bot@$USER
journalctl -u pi-inline-bot@$USER -f
```

## Configuration

All settings come from environment variables (see `bot.env.example`):

| Variable        | Default                                   | Meaning                                   |
|-----------------|-------------------------------------------|-------------------------------------------|
| `BOT_TOKEN`     | —                                         | Token from @BotFather (required)          |
| `ALLOWED_USERS` | empty (nobody)                            | Comma- or space-separated Telegram IDs    |
| `PI_BIN`        | `pi`                                      | Path to the pi binary                     |
| `PI_ARGS`       | `-p --no-session --tools read,grep,find,ls` + a short system prompt | Arguments passed to pi before `-- <query>` |
| `PI_TIMEOUT`    | `180`                                     | Seconds before pi is killed               |
| `PI_CWD`        | `$HOME`                                   | Working directory for pi                  |
| `PI_MAX_JOBS`   | `2`                                       | Max concurrent pi runs                    |

## Security

Anyone in `ALLOWED_USERS` can make pi read files that are readable by the bot's user.
Keep the list short, and think twice before adding write or shell tools to `PI_ARGS`.

## Tests

```sh
python3 -m unittest -v
```

## License

[MIT](LICENSE)
