import asyncio
import json
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Union

import discord
from discord.ext import commands

DATA_FILE = "data/antinuke.json"
ANTI_NUKE_COUNTERS = defaultdict(deque)
ACTION_NAMES = {
    "channel_create": "Channel Create",
    "channel_delete": "Channel Delete",
    "role_create": "Role Create",
    "role_delete": "Role Delete",
    "ban": "Member Ban",
}
DEFAULT_SETTINGS = {
    "enabled": False,
    "log_channel_id": None,
    "threshold": 3,
    "window_seconds": 15,
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


def register_counter(key, window_seconds: int):
    now = datetime.now(timezone.utc)
    bucket = ANTI_NUKE_COUNTERS[key]

    while bucket and (now - bucket[0]).total_seconds() > window_seconds:
        bucket.popleft()

    bucket.append(now)
    return len(bucket)


def reset_counter(key):
    ANTI_NUKE_COUNTERS[key].clear()


# -------------------------
# Cog
# -------------------------
class Antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def build_status_embed(self, guild: discord.Guild):
        settings = ensure_settings(guild.id)
        log_channel = guild.get_channel(settings.get("log_channel_id")) if settings.get("log_channel_id") else None

        embed = discord.Embed(
            title="Anti-Nuke Status",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Enabled", value=str(settings["enabled"]), inline=True)
        embed.add_field(name="Threshold", value=str(settings["threshold"]), inline=True)
        embed.add_field(name="Window", value=f'{settings["window_seconds"]}s', inline=True)
        embed.add_field(name="Punishment", value=settings["punishment"], inline=True)
        embed.add_field(
            name="Log Channel",
            value=log_channel.mention if log_channel else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Whitelist",
            value=(
                f'Users: {len(settings["whitelist_users"])}\n'
                f'Roles: {len(settings["whitelist_roles"])}'
            ),
            inline=True,
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

    async def get_audit_executor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        try:
            await asyncio.sleep(1)
            async for entry in guild.audit_logs(limit=6, action=action):
                target = getattr(entry, "target", None)
                if getattr(target, "id", None) != target_id:
                    continue

                age = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                if age > 15:
                    continue

                return entry.user
        except (discord.Forbidden, discord.HTTPException):
            return None

        return None

    async def is_whitelisted(self, guild: discord.Guild, user):
        if user is None:
            return True

        if user.id == guild.owner_id:
            return True

        if self.bot.user and user.id == self.bot.user.id:
            return True

        member = guild.get_member(user.id)
        if member is None:
            return False

        settings = ensure_settings(guild.id)
        if member.id in settings["whitelist_users"]:
            return True

        member_role_ids = {role.id for role in member.roles}
        if member_role_ids.intersection(settings["whitelist_roles"]):
            return True

        return False

    async def punish(self, guild: discord.Guild, user, punishment: str, reason: str):
        member = guild.get_member(user.id) if user else None

        try:
            if punishment == "ban":
                await guild.ban(user, reason=reason)
                return True, "ban"

            if member is None:
                return False, "member_not_found"

            if punishment == "kick":
                await member.kick(reason=reason)
                return True, "kick"

            timeout_until = datetime.now(timezone.utc) + timedelta(minutes=60)
            await member.edit(timed_out_until=timeout_until, reason=reason)
            return True, "timeout"
        except (discord.Forbidden, discord.HTTPException):
            return False, "failed"

    async def handle_action(
        self,
        guild: discord.Guild,
        action_key: str,
        audit_action: discord.AuditLogAction,
        target_id: int,
        details: str,
        cleanup=None,
    ):
        settings = ensure_settings(guild.id)
        if not settings["enabled"]:
            return

        executor = await self.get_audit_executor(guild, audit_action, target_id)
        if executor is None:
            return

        if await self.is_whitelisted(guild, executor):
            return

        key = (guild.id, executor.id, action_key)
        count = register_counter(key, settings["window_seconds"])
        if count < settings["threshold"]:
            return

        reason = f"Anti-nuke triggered for {ACTION_NAMES[action_key].lower()} spam."
        punished, mode = await self.punish(guild, executor, settings["punishment"], reason)
        reset_counter(key)

        if cleanup is not None:
            try:
                await cleanup()
            except Exception:
                pass

        result = settings["punishment"] if punished else f"no action ({mode})"
        description = (
            f"Executor: {executor} (`{executor.id}`)\n"
            f"Action: {ACTION_NAMES[action_key]}\n"
            f"Count: {count} in {settings['window_seconds']}s\n"
            f"Result: {result}\n"
            f"Details: {details}"
        )
        await self.send_log(guild, "Anti-Nuke Triggered", description, discord.Color.red())

    @commands.group(name="antinuke", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke(self, ctx):
        if not ctx.guild:
            return

        await ctx.send(embed=self.build_status_embed(ctx.guild))

    @antinuke.command(name="status")
    @commands.has_permissions(administrator=True)
    async def antinuke_status(self, ctx):
        if not ctx.guild:
            return

        await ctx.send(embed=self.build_status_embed(ctx.guild))

    @antinuke.command(name="on")
    @commands.has_permissions(administrator=True)
    async def antinuke_on(self, ctx):
        if not ctx.guild:
            return

        update_settings(ctx.guild.id, enabled=True)
        await ctx.send(embed=discord.Embed(title="Anti-Nuke Enabled", color=discord.Color.green()))

    @antinuke.command(name="off")
    @commands.has_permissions(administrator=True)
    async def antinuke_off(self, ctx):
        if not ctx.guild:
            return

        update_settings(ctx.guild.id, enabled=False)
        await ctx.send(embed=discord.Embed(title="Anti-Nuke Disabled", color=discord.Color.red()))

    @antinuke.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def antinuke_setup(
        self,
        ctx,
        log_channel: discord.TextChannel,
        threshold: int = 3,
        window_seconds: int = 15,
        punishment: str = "timeout",
    ):
        if not ctx.guild:
            return

        punishment = punishment.lower()
        if punishment not in VALID_PUNISHMENTS:
            await ctx.send("Punishment must be one of: ban, kick, timeout.")
            return

        threshold = max(1, threshold)
        window_seconds = max(5, window_seconds)

        settings = update_settings(
            ctx.guild.id,
            enabled=True,
            log_channel_id=log_channel.id,
            threshold=threshold,
            window_seconds=window_seconds,
            punishment=punishment,
        )

        embed = discord.Embed(title="Anti-Nuke Updated", color=discord.Color.green())
        embed.add_field(name="Log Channel", value=log_channel.mention, inline=False)
        embed.add_field(name="Threshold", value=str(settings["threshold"]), inline=True)
        embed.add_field(name="Window", value=f'{settings["window_seconds"]}s', inline=True)
        embed.add_field(name="Punishment", value=settings["punishment"], inline=True)
        await ctx.send(embed=embed)

    @antinuke.group(name="whitelist", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke_whitelist(self, ctx):
        if not ctx.guild:
            return

        await ctx.send("Use `antinuke whitelist add/remove/list`.")

    @antinuke_whitelist.command(name="add")
    @commands.has_permissions(administrator=True)
    async def antinuke_whitelist_add(self, ctx, target: Union[discord.Member, discord.Role]):
        if not ctx.guild:
            return

        settings = ensure_settings(ctx.guild.id)
        if isinstance(target, discord.Role):
            roles = set(settings["whitelist_roles"])
            roles.add(target.id)
            settings = update_settings(ctx.guild.id, whitelist_roles=sorted(roles))
        else:
            users = set(settings["whitelist_users"])
            users.add(target.id)
            settings = update_settings(ctx.guild.id, whitelist_users=sorted(users))

        await ctx.send(
            embed=discord.Embed(
                title="Whitelist Updated",
                description=f"Added {target.mention} to anti-nuke whitelist.",
                color=discord.Color.green(),
            )
        )

    @antinuke_whitelist.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def antinuke_whitelist_remove(self, ctx, target: Union[discord.Member, discord.Role]):
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
                description=f"Removed {target.mention} from anti-nuke whitelist.",
                color=discord.Color.orange(),
            )
        )

    @antinuke_whitelist.command(name="list")
    @commands.has_permissions(administrator=True)
    async def antinuke_whitelist_list(self, ctx):
        if not ctx.guild:
            return

        settings = ensure_settings(ctx.guild.id)
        users = [ctx.guild.get_member(user_id) for user_id in settings["whitelist_users"]]
        roles = [ctx.guild.get_role(role_id) for role_id in settings["whitelist_roles"]]

        user_text = ", ".join(member.mention for member in users if member) or "None"
        role_text = ", ".join(role.mention for role in roles if role) or "None"

        embed = discord.Embed(title="Anti-Nuke Whitelist", color=discord.Color.blurple())
        embed.add_field(name="Users", value=clip(user_text, 1024), inline=False)
        embed.add_field(name="Roles", value=clip(role_text, 1024), inline=False)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not hasattr(channel, "guild"):
            return

        async def cleanup():
            await channel.delete(reason="Anti-nuke cleanup")

        await self.handle_action(
            channel.guild,
            "channel_create",
            discord.AuditLogAction.channel_create,
            channel.id,
            f"Created channel: {channel.name} (`{channel.id}`)",
            cleanup=cleanup,
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not hasattr(channel, "guild"):
            return

        await self.handle_action(
            channel.guild,
            "channel_delete",
            discord.AuditLogAction.channel_delete,
            channel.id,
            f"Deleted channel: {channel.name} (`{channel.id}`)",
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        async def cleanup():
            await role.delete(reason="Anti-nuke cleanup")

        await self.handle_action(
            role.guild,
            "role_create",
            discord.AuditLogAction.role_create,
            role.id,
            f"Created role: {role.name} (`{role.id}`)",
            cleanup=cleanup,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self.handle_action(
            role.guild,
            "role_delete",
            discord.AuditLogAction.role_delete,
            role.id,
            f"Deleted role: {role.name} (`{role.id}`)",
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        await self.handle_action(
            guild,
            "ban",
            discord.AuditLogAction.ban,
            user.id,
            f"Banned member: {user} (`{user.id}`)",
        )


async def setup(bot):
    await bot.add_cog(Antinuke(bot))
