import discord
from discord.ext import commands
from config.prefix import DEFAULT_PREFIX
import json
import os
from datetime import datetime, timezone

AFK_FILE = "data/afk.json"
PREFIX_FILE = "data/prefixes.json"


# -------------------------
# Helpers
# -------------------------
def ensure_data():
    os.makedirs("data", exist_ok=True)


def load_json(path, default):
    ensure_data()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    ensure_data()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_afk():
    return load_json(AFK_FILE, {})


def save_afk(data):
    save_json(AFK_FILE, data)


def get_server_prefix(guild_id: int | None):
    if guild_id is None:
        return DEFAULT_PREFIX

    prefixes = load_json(PREFIX_FILE, {})
    return prefixes.get(str(guild_id), DEFAULT_PREFIX)


def format_afk_time(started_at_iso: str):
    try:
        started_at = datetime.fromisoformat(started_at_iso)
        now = datetime.now(timezone.utc)
        diff = now - started_at

        total_seconds = int(diff.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)
    except Exception:
        return "unknown time"


def add_afk_to_nick(nick: str | None, username: str):
    base = nick if nick else username

    if base.startswith("[AFK] "):
        return base

    new_nick = f"[AFK] {base}"
    return new_nick[:32]


def remove_afk_from_nick(nick: str | None):
    if not nick:
        return None

    if nick.startswith("[AFK] "):
        return nick[6:]

    return nick


# -------------------------
# Cog
# -------------------------
class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="afk")
    async def afk(self, ctx, *, reason: str = "AFK"):
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        data = load_afk()
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        if guild_id not in data:
            data[guild_id] = {}

        data[guild_id][user_id] = {
            "reason": reason,
            "since": datetime.now(timezone.utc).isoformat(),
            "name": str(ctx.author),
            "old_nick": ctx.author.nick
        }
        save_afk(data)

        # add [AFK] to nickname
        try:
            new_nick = add_afk_to_nick(ctx.author.nick, ctx.author.name)
            if ctx.author.guild_permissions.change_nickname or ctx.guild.me.guild_permissions.manage_nicknames:
                await ctx.author.edit(nick=new_nick, reason="AFK enabled")
        except Exception:
            pass

        embed = discord.Embed(
            title="💤 AFK Set",
            description=f"{ctx.author.mention} is now AFK.\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        prefix = get_server_prefix(message.guild.id if message.guild else None)

        # Don't instantly remove AFK when using the AFK command
        if message.content.lower().startswith(f"{prefix}afk"):
            return

        data = load_afk()

        # Remove AFK when user sends a normal message
        if guild_id in data and user_id in data[guild_id]:
            afk_info = data[guild_id].pop(user_id)

            if not data[guild_id]:
                del data[guild_id]

            save_afk(data)

            afk_time = format_afk_time(afk_info.get("since", ""))

            # restore nickname
            try:
                old_nick = afk_info.get("old_nick")
                if message.guild.me.guild_permissions.manage_nicknames:
                    await message.author.edit(nick=old_nick, reason="AFK removed")
            except Exception:
                pass

            embed = discord.Embed(
                title="✅ Welcome Back",
                description=(
                    f"{message.author.mention}, your AFK has been removed.\n"
                    f"You were AFK for **{afk_time}**."
                ),
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)

        # reload AFK data after possible removal
        data = load_afk()
        guild_data = data.get(guild_id, {})

        if not message.mentions:
            return

        already_sent = set()

        for member in message.mentions:
            if member.bot:
                continue

            member_id = str(member.id)

            if member_id in guild_data and member.id not in already_sent:
                afk_info = guild_data[member_id]
                afk_reason = afk_info.get("reason", "AFK")
                afk_time = format_afk_time(afk_info.get("since", ""))

                embed = discord.Embed(
                    title="💤 User is AFK",
                    description=(
                        f"{member.mention} is currently AFK.\n"
                        f"**Reason:** {afk_reason}\n"
                        f"**Since:** {afk_time} ago"
                    ),
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=embed)
                already_sent.add(member.id)

    @afk.error
    async def afk_error(self, ctx, error):
        prefix = get_server_prefix(ctx.guild.id if ctx.guild else None)

        if isinstance(error, commands.TooManyArguments):
            await ctx.send(f"Usage: `{prefix}afk [reason]`")


# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(AFK(bot))