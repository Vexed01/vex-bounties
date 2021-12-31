from redbot.core.bot import Red

from .cpu import CPU


async def setup(bot: Red) -> None:
    cog = CPU(bot)
    await cog.init_api()
    bot.add_cog(cog)
