from discord.ext import commands

class ExtensionsFailed(ExceptionGroup[commands.ExtensionFailed]): pass

def not_none[T](obj: T | None) -> T:
    assert obj is not None
    return obj