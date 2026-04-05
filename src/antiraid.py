import json
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Union

import discord
from discord.ext import commands

DATA_FILE = "data/antiraid.json"
JOIN_COUNTERS = defaultdict(deque)
MESSAGE_COUNTERS = defaultdict(deque)
DEFAULT_SETTINGS = {
    "enabled": False,
    "log_channel_id": None,
    "join_threshold": 5,
    "join_window_seconds": 20,
    "account_age_minutes": 30,
    "mention_limit": 8,
    "spam_threshold": 6,
    "spam_window_seconds": 8,
    "punishment": "timeout",
    "timeout_minutes": 60,
    "whitelist_users": [],
    "whitelist_roles": [],
}
VALID_PUNISHMENTS = {"ban", "kick", "timeout"}


# -------------------------
# Helpers
# -------------------------
def ensure_data():
    os.makedirs("data", exist_ok=True)


def load_json():
    ensure_data()
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(data):
    ensure_data()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def ensure_settings(guild_id: int):
    data = load_json()
    settings = data.setdefault(str(guild_id), {})
    changed = False

    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
            changed = True

    if changed:
        save_json(data)

    return settings


def update_settings(guild_id: int, **changes):
    data = load_json()
    settings = data.setdefault(str(guild_id), {})

    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)

    settings.update(changes)
    data[str(guild_id)] = settings
    save_json(data)
    return settings


def clip(text, limit):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def register_counter(counter, key, window_seconds: int):
    now = datetime.now(timezone.utc)
    bucket = counter[key]

    while bucket and (now - bucket[0]).total_seconds() > window_seconds:
        bucket.popleft()

    bucket.append(now)
    return len(bucket)


def reset_counter(counter, key):
    counter[key].clear()


# -------------------------
# Cog
# -------------------------
class Antiraid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def build_status_embed(self, guild: discord.Guild):
        settings = ensure_settings(guild.id)
        log_channel = guild.get_channel(settings.get("log_channel_id")) if settings.get("log_channel_id") else None

        embed = discord.Embed(
            title="Anti-Raid Status",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Enabled", value=str(settings["enabled"]), inline=True)
        embed.add_field(name="Punishment", value=settings["punishment"], inline=True)
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not set", inline=True)
        embed.add_field(
            name="Join Flood",
            value=f'{settings["join_threshold"]} joins / {settings["join_window_seconds"]}s',
            inline=False,
        )
        embed.add_field(
            name="Account Age",
            value=f'{settings["account_age_minutes"]} minute minimum',
            inline=True,
        )
        embed.add_field(
            name="Mention Limit",
            value=str(settings["mention_limit"]),
            inline=True,
        )
        embed.add_field(
            name="Spam Limit",
            value=f'{settings["spam_threshold"]} messages / {settings["spam_window_seconds"]}s',
            inline=True,
        )
        embed.add_field(
            name="Whitelist",
            value=(
                f'Users: {len(settings["whitelist_users"])}\n'
                f'Roles: {len(settings["whitelist_roles"])}'
            ),
            inline=False,
        )
        return embed

    async def send_log(self, guild: discord.Guild, title: str, description: str, color: discord.Color):
        settings = ensure_settings(guild.id)
        channel_id = settings.get("log_channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        embed = discord.Embed(
            title=title,
            description=clip(description, 4000),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    async def is_whitelisted(self, guild: discord.Guild, member: discord.Member):
        if member.id == guild.owner_id:
            return True

        if self.bot.user and member.id == self.bot.user.id:
            return True

        settings = ensure_settings(guild.id)
        if member.id in settings["whitelist_users"]:
            return True

        member_role_ids = {role.id for role in member.roles}
        if member_role_ids.intersection(settings["whitelist_roles"]):
            return True

        return False

    async def punish(self, guild: discord.Guild, member: discord.Member, punishment: str, reason: str):
        try:
            if punishment == "ban":
                await guild.ban(member, reason=reason)
                return True, "ban"

            if punishment == "kick":
                await member.kick(reason=reason)
                return True, "kick"

            timeout_until = datetime.now(timezone.utc) + timedelta(minutes=60)
            await member.edit(timed_out_until=timeout_until, reason=reason)
            return True, "timeout"
        except (discord.Forbidden, discord.HTTPException):
            return False, "failed"

    @commands.group(name="antiraid", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antiraid(self, ctx):
        if not ctx.guild:
            return

        await ctx.send(embed=self.build_status_embed(ctx.guild))

    @antiraid.command(name="status")
    @commands.has_permissions(administrator=True)
    async def antiraid_status(self, ctx):
        if not ctx.guild:
            return

        await ctx.send(embed=self.build_status_embed(ctx.guild))

    @antiraid.command(name="on")
    @commands.has_permissions(administrator=True)
    async def antiraid_on(self, ctx):
        if not ctx.guild:
            return

        update_settings(ctx.guild.id, enabled=True)
        await ctx.send(embed=discord.Embed(title="Anti-Raid Enabled", color=discord.Color.green()))

    @antiraid.command(name="off")
    @commands.has_permissions(administrator=True)
    async def antiraid_off(self, ctx):
        if not ctx.guild:
            return

        update_settings(ctx.guild.id, enabled=False)
        await ctx.send(embed=discord.Embed(title="Anti-Raid Disabled", color=discord.Color.red()))

    @antiraid.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def antiraid_setup(
        self,
        ctx,
        log_channel: discord.TextChannel,
        join_threshold: int = 5,
        join_window_seconds: int = 20,
        account_age_minutes: int = 30,
        punishment: str = "timeout",
    ):
        if not ctx.guild:
            return

        punishment = punishment.lower()
        if punishment not in VALID_PUNISHMENTS:
            await ctx.send("Punishment must be one of: ban, kick, timeout.")
            return

        settings = update_settings(
            ctx.guild.id,
            enabled=True,
            log_channel_id=log_channel.id,
            join_threshold=max(2, join_threshold),
            join_window_seconds=max(5, join_window_seconds),
            account_age_minutes=max(0, account_age_minutes),
            punishment=punishment,
        )

        embed = discord.Embed(title="Anti-Raid Updated", color=discord.Color.green())
        embed.add_field(name="Log Channel", value=log_channel.mention, inline=False)
        embed.add_field(
            name="Join Flood",
            value=f'{settings["join_threshold"]} joins / {settings["join_window_seconds"]}s',
            inline=False,
        )
        embed.add_field(
            name="Account Age",
            value=f'{settings["account_age_minutes"]} minute minimum',
            inline=True,
        )
        embed.add_field(name="Punishment", value=settings["punishment"], inline=True)
        await ctx.send(embed=embed)

    @antiraid.command(name="joins")
    @commands.has_permissions(administrator=True)
    async def antiraid_joins(self, ctx, threshold: int, window_seconds: int = 20):
        if not ctx.guild:
            return

        threshold = max(2, threshold)
        window_seconds = max(5, window_seconds)
        update_settings(
            ctx.guild.id,
            join_threshold=threshold,
            join_window_seconds=window_seconds,
        )
        await ctx.send(
            embed=discord.Embed(
                title="Join Flood Protection Updated",
                description=(
                    f"Join flood protection will trigger at `{threshold}` joins in "
                    f"`{window_seconds}` seconds."
                ),
                color=discord.Color.green(),
            )
        )

    @antiraid.command(name="mentions")
    @commands.has_permissions(administrator=True)
    async def antiraid_mentions(self, ctx, limit: int):
        if not ctx.guild:
            return

        limit = max(1, limit)
        update_settings(ctx.guild.id, mention_limit=limit)
        await ctx.send(
            embed=discord.Embed(
                title="Mention Protection Updated",
                description=f"Mass-mention protection will trigger at `{limit}` mentions.",
                color=discord.Color.green(),
            )
        )

    @antiraid.command(name="spam")
    @commands.has_permissions(administrator=True)
    async def antiraid_spam(self, ctx, threshold: int, window_seconds: int = 8):
        if not ctx.guild:
            return

        update_settings(
            ctx.guild.id,
            spam_threshold=max(2, threshold),
            spam_window_seconds=max(3, window_seconds),
        )
        await ctx.send(
            embed=discord.Embed(
                title="Spam Protection Updated",
                description=(
                    f"Spam protection will trigger at `{max(2, threshold)}` messages in "
                    f"`{max(3, window_seconds)}` seconds."
                ),
                color=discord.Color.green(),
            )
        )

    @antiraid.command(name="accountage")
    @commands.has_permissions(administrator=True)
    async def antiraid_accountage(self, ctx, minutes: int):
        if not ctx.guild:
            return

        minutes = max(0, minutes)
        update_settings(ctx.guild.id, account_age_minutes=minutes)
        await ctx.send(
            embed=discord.Embed(
                title="Account Age Protection Updated",
                description=f"New accounts younger than `{minutes}` minutes will be flagged.",
                color=discord.Color.green(),
            )
        )

    @antiraid.command(name="punishment")
    @commands.has_permissions(administrator=True)
    async def antiraid_punishment(self, ctx, punishment: str):
        if not ctx.guild:
            return

        punishment = punishment.lower()
        if punishment not in VALID_PUNISHMENTS:
            await ctx.send("Punishment must be one of: ban, kick, timeout.")
            return

        update_settings(ctx.guild.id, punishment=punishment)
        await ctx.send(
            embed=discord.Embed(
                title="Anti-Raid Punishment Updated",
                description=f"Punishment is now set to `{punishment}`.",
                color=discord.Color.green(),
            )
        )

    @antiraid.group(name="whitelist", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antiraid_whitelist(self, ctx):
        if not ctx.guild:
            return

        await ctx.send("Use `antiraid whitelist add/remove/list`.")

    @antiraid_whitelist.command(name="add")
    @commands.has_permissions(administrator=True)
    async def antiraid_whitelist_add(self, ctx, target: Union[discord.Member, discord.Role]):
        if not ctx.guild:
            return

        settings = ensure_settings(ctx.guild.id)
        if isinstance(target, discord.Role):
            roles = set(settings["whitelist_roles"])
            roles.add(target.id)
            update_settings(ctx.guild.id, whitelist_roles=sorted(roles))
        else:
            users = set(settings["whitelist_users"])
            users.add(target.id)
            update_settings(ctx.guild.id, whitelist_users=sorted(users))

        await ctx.send(
            embed=discord.Embed(
                title="Whitelist Updated",
                description=f"Added {target.mention} to anti-raid whitelist.",
                color=discord.Color.green(),
            )
        )

    @antiraid_whitelist.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def antiraid_whitelist_remove(self, ctx, target: Union[discord.Member, discord.Role]):
        if not ctx.guild:
            return

        settings = ensure_settings(ctx.guild.id)
        if isinstance(target, discord.Role):
            roles = set(settings["whitelist_roles"])
            roles.discard(target.id)
            update_settings(ctx.guild.id, whitelist_roles=sorted(roles))
        else:
            users = set(settings["whitelist_users"])
            users.discard(target.id)
            update_settings(ctx.guild.id, whitelist_users=sorted(users))

        await ctx.send(
            embed=discord.Embed(
                title="Whitelist Updated",
                description=f"Removed {target.mention} from anti-raid whitelist.",
                color=discord.Color.orange(),
            )
        )

    @antiraid_whitelist.command(name="list")
    @commands.has_permissions(administrator=True)
    async def antiraid_whitelist_list(self, ctx):
        if not ctx.guild:
            return

        settings = ensure_settings(ctx.guild.id)
        users = [ctx.guild.get_member(user_id) for user_id in settings["whitelist_users"]]
        roles = [ctx.guild.get_role(role_id) for role_id in settings["whitelist_roles"]]

        user_text = ", ".join(member.mention for member in users if member) or "None"
        role_text = ", ".join(role.mention for role in roles if role) or "None"

        embed = discord.Embed(title="Anti-Raid Whitelist", color=discord.Color.blurple())
        embed.add_field(name="Users", value=clip(user_text, 1024), inline=False)
        embed.add_field(name="Roles", value=clip(role_text, 1024), inline=False)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = ensure_settings(member.guild.id)
        if not settings["enabled"]:
            return

        if await self.is_whitelisted(member.guild, member):
            return

        account_age = datetime.now(timezone.utc) - member.created_at
        if account_age < timedelta(minutes=settings["account_age_minutes"]):
            punished, mode = await self.punish(
                member.guild,
                member,
                settings["punishment"],
                "Anti-raid account age protection triggered.",
            )
            result = settings["punishment"] if punished else f"no action ({mode})"
            await self.send_log(
                member.guild,
                "Anti-Raid Triggered",
                (
                    f"Member: {member} (`{member.id}`)\n"
                    f"Reason: Account age below minimum\n"
                    f"Account age: {int(account_age.total_seconds() // 60)} minute(s)\n"
                    f"Result: {result}"
                ),
                discord.Color.red(),
            )
            return

        join_count = register_counter(JOIN_COUNTERS, member.guild.id, settings["join_window_seconds"])
        if join_count < settings["join_threshold"]:
            return

        punished, mode = await self.punish(
            member.guild,
            member,
            settings["punishment"],
            "Anti-raid join flood protection triggered.",
        )
        result = settings["punishment"] if punished else f"no action ({mode})"
        await self.send_log(
            member.guild,
            "Anti-Raid Triggered",
            (
                f"Member: {member} (`{member.id}`)\n"
                f"Reason: Join flood detected\n"
                f"Count: {join_count} joins in {settings['join_window_seconds']}s\n"
                f"Result: {result}"
            ),
            discord.Color.red(),
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not isinstance(message.author, discord.Member):
            return

        settings = ensure_settings(message.guild.id)
        if not settings["enabled"]:
            return

        if await self.is_whitelisted(message.guild, message.author):
            return

        key = (message.guild.id, message.author.id)
        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count >= settings["mention_limit"]:
            reset_counter(MESSAGE_COUNTERS, key)

            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            punished, mode = await self.punish(
                message.guild,
                message.author,
                settings["punishment"],
                "Anti-raid mass mention protection triggered.",
            )
            result = settings["punishment"] if punished else f"no action ({mode})"
            await self.send_log(
                message.guild,
                "Anti-Raid Triggered",
                (
                    f"Member: {message.author} (`{message.author.id}`)\n"
                    f"Reason: Mass mention detected\n"
                    f"Mentions: {mention_count}\n"
                    f"Result: {result}"
                ),
                discord.Color.red(),
            )
            return

        spam_count = register_counter(MESSAGE_COUNTERS, key, settings["spam_window_seconds"])
        if spam_count < settings["spam_threshold"]:
            return

        reset_counter(MESSAGE_COUNTERS, key)

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        punished, mode = await self.punish(
            message.guild,
            message.author,
            settings["punishment"],
            "Anti-raid spam protection triggered.",
        )
        result = settings["punishment"] if punished else f"no action ({mode})"
        await self.send_log(
            message.guild,
            "Anti-Raid Triggered",
            (
                f"Member: {message.author} (`{message.author.id}`)\n"
                f"Reason: Message spam detected\n"
                f"Count: {spam_count} messages in {settings['spam_window_seconds']}s\n"
                f"Result: {result}"
            ),
            discord.Color.red(),
        )


async def setup(bot):
    await bot.add_cog(Antiraid(bot))
