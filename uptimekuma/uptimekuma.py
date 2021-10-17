import asyncio
import logging
from typing import Literal, Optional

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from aiohttp import web

log = logging.getLogger("red.vex-bounty.uptimekuma")

class UptimeKuma(commands.Cog):
    """
    A cog for responding to Uptime Kuma pings, which could be used for most uptime monitoring services.

    The web server will run in the background whenever the cog is loaded on the specified port.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=418078199982063626,
            force_registration=True
        )
        self.config.register_global(port=8710)

    def cog_unload(self):
        self.bot.loop.create_task(self.shutdown_webserver())

    async def shutdown_webserver(self) -> None:
        await self.runner.shutdown()
        await self.runner.cleanup()
        log.info("Web server for Uptime Kuma pings has been stopped due to cog unload.")

    async def red_delete_data_for_user(self, *args, **kwargs) -> None:
        # nothing to delete
        pass

    async def main_page(self, request: web.Request) -> web.Response:
        return web.Response(text=f"{self.bot.user.name} is online and the UptimeKuma cog is loaded.", status=200)

    async def start_webserver(self) -> None:
        await asyncio.sleep(1)  # let previous server shut down if cog was reloaded

        app = web.Application()
        app.add_routes([web.get("/", self.main_page)])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, port=await self.config.port())
        await site.start()

        log.info(f"Web server for Uptime Kuma pings has started on port {await self.config.port()}.")

        self.runner = runner

    @commands.is_owner()
    @commands.command()
    async def kumaport(self, ctx: commands.Context, port: Optional[int] = None):
        """Get or set the port to run the simple web server on.

        Run the command on it's own (`[p]kumaport`) to see what it's set to at the moment,
        and to set it run `[p]kumaport 8080`, for example.
        """
        if port is None:
            await ctx.send(
                f"The current port is {await self.config.port()}.\nTo change it, run "
                f"`{ctx.clean_prefix}kumaport <port>`"
            )
            return

        async with ctx.typing():
            await self.config.port.set(port)
            await self.shutdown_webserver()
            await self.start_webserver()

        await ctx.send(f"The webserver has been restarted on port {port}.")
