from redbot.core.bot import Red

from .cpu import CPU


async def setup(bot: Red) -> None:
    cog = CPU(bot)
    await cog.init_api()
    r = bot.add_cog(cog)
    if r is not None:  # simultaneous Red 3.4 & 3.5 compatibility
        await r
