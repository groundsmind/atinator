# atinator

discord bot that reimplements the @someone april fools' feature

[**invite**](https://discord.com/oauth2/authorize?client_id=1541883116690350170)

## how it works

the bot adds one role to any guild it is added to, named "someone" by default (no shit). the role only holds one person at a time, and a new person is chosen every time it is pinged. ~~this makes it so you can see who will be pinged next time but whatever~~

internally, the bot stores a bag of members queued to be @someone (this is outlined somewhere in [cogs/someone.py](cogs/someone.py))

## self-hosting

> [!NOTE]
> if you host this, please let me know (@network.address.translation)!

**you must enable the Server Members and Message Content privileged gateway intents!** additionally, the bot will need at least the **Manage Roles permission**.

to provide the token, either set and export an environment variable `TOKEN`, or add a `.env` file:
```
TOKEN=[the bot's token]
```

to the install the dependencies (using a [venv](https://docs.python.org/3/tutorial/venv.html) is recommended, especially on Linux):
```
$ pip install -r requirements.txt
```

to run it:
```
$ python3 atinator
```

### configuration

a few other options can be set alongside `TOKEN` (default values in parentheses):
- `COMMAND_PREFIXES` (`at!,sone!`): comma-separated list of prefixes for text commands (escape commas with a backslash)
- `DB_URL` (`sqlite+aiosqlite:///db.sqlite`): the database URL in [SQLAlchemy's format](https://docs.sqlalchemy.org/en/stable/core/engines.html#database-urls). the dialect must support async
