import asyncio
import logging
from typing import List, Optional, Tuple

import discord
from rapidfuzz import process
from redbot.core import commands
from redbot.core.utils import deduplicate_iterables
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .scraper import FullCPU, PassMarkScrapeAPI

ZERO_WIDTH = "\u200b"

log = logging.getLogger("red.vex-bounty.cpu")


class CPU(commands.Cog):
    """
    View PassMark CPU benchmarks.

    Data is for personal, non-commercial use only.
    https://www.passmark.com/legal/disclaimer.php
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def cog_unload(self):
        asyncio.create_task(self.api.session.close())

    async def init_api(self) -> None:
        """Initialize the API session."""
        self.api = PassMarkScrapeAPI()
        try:
            await self.api.get_full_list()  # this is then cached for later use
        except Exception as e:
            log.error(f"Failed to get the initial CPU list", exc_info=e)

    async def find_matches(self, cpu: str) -> List[Tuple[str, float, int]]:
        """Find the top 9 matches for a CPU name, if any."""
        cpus = await self.api.get_full_list()  # this is cached
        cpu_names = [cpu["name"] for cpu in cpus]

        matches = process.extract(cpu, cpu_names, score_cutoff=80, limit=9)
        return matches

    async def find_match(self, cpu: str) -> Optional[Tuple[str, float, int]]:
        """Find the best match for a CPU name, if any."""
        cpus = await self.api.get_full_list()  # this is cached
        cpu_names = [cpu["name"] for cpu in cpus]

        match = process.extractOne(cpu, cpu_names, score_cutoff=90)
        return match

    @commands.command()
    async def cpu(self, ctx: commands.Context, *, cpu: str) -> None:
        """View PassMark CPU benchmark for a CPU."""
        async with ctx.typing():
            try:
                match = await self.find_match(cpu)
            except Exception as e:
                log.error(
                    "Something went wrong finding a match - probably a scraping error",
                    exc_info=e,
                )
                await ctx.send("Something went wrong getting data from PassMark. Try again later.")
                return
            if match is None:
                await ctx.send(
                    f"Sorry, no matches found. Try again or use the `{ctx.clean_prefix}cpusearch` command."
                )
                return

            cpus = await self.api.get_full_list()  # this is cached
            partial_cpu = cpus[match[2]]
            try:
                full_cpu = await self.api.get_cpu_info(partial_cpu)
            except Exception as e:
                log.error("Something went wrong getting the full CPU info", exc_info=e)
                await ctx.send("Something went wrong getting data from PassMark. Try again later.")
                return

            embed = discord.Embed()
            embed.colour = await ctx.embed_colour()
            embed.title = full_cpu["name"]
            embed.description = f"[View on PassMark]({full_cpu['url']})"
            embed.set_footer(text=f"Use {ctx.clean_prefix}compare to compare CPUs.")

            for key, value in full_cpu["details"].items():
                if value is None or value == "":
                    value = "Unknown"
                embed.add_field(name=key, value=value)

        await ctx.send(embed=embed)

    @commands.command()
    async def compare(self, ctx: commands.Context, *, cpus: str) -> None:
        """
        Compare multiple CPUs, seperated by a comma.

        You can only compare 2.

        Example: `[p]compare Ryzen 5 1600, Ryzen 5 1600X`
        """
        unmatched_cpus = cpus.split(",")
        if len(unmatched_cpus) != 2:
            await ctx.send("Sorry, I can only compare 2 CPUs. Separate them with commas (`,`).")
            return

        matched_cpus: List[FullCPU] = []
        available_specs = []

        async with ctx.typing():
            all_cpus = await self.api.get_full_list()  # this is cached

            for cpu in unmatched_cpus:
                try:
                    match = await self.find_match(cpu.strip())
                except Exception as e:
                    log.error(
                        "Something went wrong finding a match - probably a scraping error",
                        exc_info=e,
                    )
                    await ctx.send(
                        "Something went wrong getting data from PassMark. Try again later."
                    )
                    return
                if match is None:
                    await ctx.send(
                        f"Sorry, no matches found for `{cpu}`. Try again or use the `{ctx.clean_prefix}cpusearch` command."
                    )
                    return

                partial_cpu = all_cpus[match[2]]
                try:
                    full_cpu = await self.api.get_cpu_info(partial_cpu)
                except Exception as e:
                    log.error("Something went wrong getting the full CPU info", exc_info=e)
                    await ctx.send(
                        "Something went wrong getting data from PassMark. Try again later."
                    )
                    return
                matched_cpus.append(full_cpu)

                for spec in full_cpu["details"].keys():
                    available_specs.append(spec)

        available_specs = deduplicate_iterables(available_specs)  # cant use set bc retain order

        embed = discord.Embed()
        embed.colour = await ctx.embed_colour()
        embed.title = "CPU Comparison"

        embed.add_field(name="Specifications", value="_ _\n" * 2 + "\n".join(available_specs))

        for cpu in matched_cpus:
            speclist = ""
            for spec in available_specs:
                value = cpu["details"].get(spec)
                speclist += (value or "-") + "\n"

            embed.add_field(
                name=cpu["name"],
                value=f"[View on PassMark]({cpu['url']})" + "\n\n" + speclist,
            )

        await ctx.send(embed=embed)

    @commands.command()
    async def cpusearch(self, ctx: commands.Context, *, query: str) -> None:
        """Get up to 9 CPUs from a search query."""
        all_cpus = await self.api.get_full_list()  # this is cached

        matches = await self.find_matches(query)
        if len(matches) == 0:
            await ctx.send("Sorry, no matches found.")
            return

        embed = discord.Embed()
        embed.title = "CPU Search Results"
        embed.colour = await ctx.embed_colour()

        desc = ""
        for i, result in enumerate(matches):
            partial_cpu = all_cpus[result[2]]
            desc += f"{i + 1}. [{partial_cpu['name']}]({partial_cpu['url']})\n"

        embed.description = desc
        embed.set_footer(
            text=f"Use {ctx.clean_prefix}cpu <name> or click the reactions to view a CPU."
        )

        message: discord.Message = await ctx.send(embed=embed)
        emojis = ReactionPredicate.NUMBER_EMOJIS[1 : len(matches) + 1]
        start_adding_reactions(message, emojis)

        pred = ReactionPredicate.with_emojis(emojis, message, ctx.author)
        try:
            await self.bot.wait_for("reaction_add", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            return

        name = matches[pred.result][0]
        await self.cpu(ctx, cpu=name)
