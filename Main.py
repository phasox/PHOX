from __future__ import annotations

import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import logging
import sys
import time
from datetime import datetime

if os.name == "nt":
    os.system("")

logging.getLogger().handlers.clear()
logging.basicConfig(level=logging.CRITICAL, format="%(message)s")

for name in ["discord", "discord.client", "discord.gateway", "asyncio"]:
    logging.getLogger(name).setLevel(logging.CRITICAL)

RESET = "\033[0m"
BOLD = "\033[1m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GOLD = "\033[38;5;220m"
GRAY = "\033[90m"

ASCII_BANNER = rf"""{GOLD}
 _______  ____  ____   ___   ____  ____  
|_   __ \|_   ||   _|.'   `.|_  _||_  _| 
  | |__) | | |__| | /  .-.  \ \ \  / /   
  |  ___/  |  __  | | |   | |  > `' <    
 _| |_    _| |  | |_\  `-'  /_/ /'`\ \_  
|_____|  |____||____|`.___.'|____||____| 
                                         
{RESET}"""

LOADED_COGS: list[str] = []
FAILED_COGS: list[tuple[str, str]] = []


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_line(tag: str, message: str, color: str = WHITE) -> None:
    print(f"{GRAY}[{now()}]{RESET} {color}{BOLD}[{tag}]{RESET} {message}")


def divider(color: str = GRAY) -> None:
    print(f"{color}{'=' * 72}{RESET}")


def spinner(text: str, duration: float = 0.5, color: str = CYAN) -> None:
    frames = ["|", "/", "-", "\\"]
    end_time = time.time() + duration
    i = 0

    while time.time() < end_time:
        sys.stdout.write(
            f"\r{GRAY}[{now()}]{RESET} {color}{BOLD}[BOOT]{RESET} {text} {frames[i % len(frames)]}"
        )
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1

    sys.stdout.write("\r")
    sys.stdout.flush()


def print_banner() -> None:
    print(ASCII_BANNER)
    divider(GOLD)
    log_line("SYSTEM", "PhaseBot Boot Manager", GOLD)
    divider(GOLD)


try:
    from config.token import TOKEN
except Exception:
    print("❌ Please Set The Bot Token in config/token.py")
    raise SystemExit

try:
    from config.prefix import DEFAULT_PREFIX
except Exception:
    print("❌ Please Set DEFAULT_PREFIX in config/prefix.py")
    raise SystemExit

if not TOKEN or TOKEN == "":
    print("❌ Please Set The Bot Token in config/token.py")
    raise SystemExit

PREFIX_FILE = "data/prefixes.json"


def get_prefix(bot, message):
    if not message.guild:
        return DEFAULT_PREFIX

    try:
        with open(PREFIX_FILE, "r", encoding="utf-8") as f:
            prefixes = json.load(f)
    except Exception:
        prefixes = {}

    return prefixes.get(str(message.guild.id), DEFAULT_PREFIX)


intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=None
)

bot.start_time = time.time()


async def load_cogs():
    if not os.path.exists("./src"):
        log_line("WARN", "src folder not found", YELLOW)
        return

    py_files = [file for file in os.listdir("./src") if file.endswith(".py")]
    total = len(py_files)

    if total == 0:
        log_line("WARN", "No cogs found in ./src", YELLOW)
        return

    divider(BLUE)
    log_line("BOOT", f"Loading {total} src(s)...", BLUE)
    divider(BLUE)

    for index, file in enumerate(py_files, start=1):
        name = file[:-3]
        spinner(f"Loading [{index}/{total}] src.{name}", 0.25, CYAN)

        try:
            await bot.load_extension(f"src.{name}")
            LOADED_COGS.append(name)
            log_line("LOADED", f"[{index}/{total}] src.{name}", GREEN)
        except Exception as e:
            FAILED_COGS.append((name, repr(e)))
            log_line("FAILED", f"[{index}/{total}] src.{name}", RED)
            print(f"           {GRAY}└─ {repr(e)}{RESET}")

    divider(BLUE)
    log_line("SUMMARY", f"Loaded : {len(LOADED_COGS)}", GREEN)
    log_line("SUMMARY", f"Failed : {len(FAILED_COGS)}", RED if FAILED_COGS else GREEN)
    divider(BLUE)


@tasks.loop(seconds=120)
async def update_status():
    servers = len(bot.guilds)
    users = sum(g.member_count or 0 for g in bot.guilds)

    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"〣Trusted In {servers} Servers ◈ By {users} Users"
    )

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=activity
    )


@bot.event
async def on_ready():
    divider(GREEN)
    log_line("READY", f"Logged in as : {bot.user}", GREEN)
    log_line("READY", f"Bot ID       : {bot.user.id if bot.user else 'unknown'}", GREEN)
    log_line("READY", f"Servers      : {len(bot.guilds)}", GREEN)
    log_line("READY", f"Users        : {sum(g.member_count or 0 for g in bot.guilds)}", GREEN)
    log_line("READY", f"Prefix       : dynamic / default = {DEFAULT_PREFIX}", GREEN)
    divider(GREEN)

    log_line("INFO", "PHOX is ready", GOLD)
    log_line("DEV", "Made By PhaseDev", MAGENTA)

    log_line("COGS", "Loaded modules:", GREEN)
    if LOADED_COGS:
        for cog in LOADED_COGS:
            log_line("OK", f"src.{cog}", GREEN)
    else:
        log_line("WARN", "No cogs loaded", YELLOW)

    log_line("COGS", "Failed modules:", RED)
    if FAILED_COGS:
        for cog, error in FAILED_COGS:
            log_line("FAIL", f"src.{cog}", RED)
            print(f"           {GRAY}└─ {error}{RESET}")
    else:
        log_line("OK", "No failed cogs", GREEN)

    if not update_status.is_running():
        update_status.start()
        log_line("STATUS", "DND status loop started", CYAN)

    uptime = round(time.time() - bot.start_time, 2)
    divider(GOLD)
    log_line("ONLINE", f"PhaseBot online in {uptime}s", GOLD)
    divider(GOLD)


async def main():
    print_banner()
    spinner("Checking configuration", 0.4, GOLD)
    log_line("BOOT", "Configuration loaded", GREEN)

    async with bot:
        await load_cogs()
        spinner("Connecting to Discord", 0.6, MAGENTA)
        log_line("BOOT", "Starting bot...", MAGENTA)
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        divider(RED)
        log_line("STOP", "PhaseBot shutdown requested", RED)
        divider(RED)
        sys.exit(0)