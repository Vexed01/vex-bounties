from typing import Dict, List, Tuple, TypedDict

import aiohttp
import bs4
from asyncache import cached
from cachetools import TTLCache

user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/96.0.4664.55 Safari/537.36 Edg/96.0.1054.43"
)


class PartialCPU(TypedDict):
    name: str
    url: str


class FullCPU(TypedDict):
    name: str
    url: str
    details: Dict[str, str]


class PassMarkScrapeAPI:
    def __init__(self) -> None:
        self.session = aiohttp.ClientSession(headers={"User-Agent": user_agent})

    @cached(TTLCache(maxsize=64, ttl=60 * 60 * 48))  # 48h LRU cache
    async def get_soup(self, url: str) -> bs4.BeautifulSoup:
        """ "I NEED SOUP!!! GIMME SOUP NOW!!!"""
        async with self.session.get(url) as resp:
            soup = bs4.BeautifulSoup(await resp.text(), "html.parser")
        return soup

    @cached(TTLCache(maxsize=1, ttl=60 * 60 * 4))  # 4h cache
    async def get_full_list(self) -> List[PartialCPU]:
        async with self.session.get("https://www.cpubenchmark.net/cpu_list.php") as resp:
            soup = bs4.BeautifulSoup(await resp.text(), "html.parser")

        table = soup.find("table", {"class": "cpulist"})
        tbody = table.find("tbody")
        cpus = tbody.find_all("tr")

        full_list: List[PartialCPU] = []

        for cpu in cpus:
            items = cpu.find_all("td")
            name = items[0].text
            url = "https://www.cpubenchmark.net/" + items[0].find("a")["href"].replace(
                "cpu_lookup", "cpu"
            )
            full_list.append(dict(name=name, url=url))

        return full_list

    async def get_cpu_info(self, cpu: PartialCPU) -> FullCPU:
        soup = await self.get_soup(cpu["url"])

        def process(s: str) -> Tuple[str, str]:
            return (
                s.split("</strong>")[0],
                s.split("</strong>")[1].lstrip(" ").split("</p>")[0],
            )

        specs = soup.find_all("div", {"class": "left-desc-cpu"})
        nicespecs = str(specs).split("<strong>")  # this works best for reasons

        details = {}

        cpu_mark = soup.find("div", {"class": "right-desc"})
        details["Multithread Rating:"] = (
            str(cpu_mark).split("Multithread Rating</div>")[1].split('">')[1].split("</div>")[0]
        )
        details["Single Thread Rating:"] = (
            str(cpu_mark).split("Single Thread Rating</div>")[1].split('">')[1].split("</div>")[0]
        )

        for spec in nicespecs:
            try:
                name, value = process(spec)
            except Exception:
                continue
            if name == "Description":
                continue

            if not name.endswith(":"):
                name += ":"

            if value.startswith(": "):
                value = value[2:]

            details[name] = value.replace("<br>", "\n").replace("</br>", "").replace("<br/>", "")

        footer = soup.find_all("div", {"class": "desc-foot"})
        imlazy = str(footer).split("CPU First Seen on Charts:")[1]

        details["First Seen:"] = process(imlazy)[1]

        return dict(
            name=cpu["name"],
            url=cpu["url"],
            details=details,
        )
