import discord
from discord.ext import commands
import asyncio
import re
import json
import os
from config.prefix import DEFAULT_PREFIX

MUTE_FILE = "data/mute.json"

# -------------------------
# Utility functions
# -------------------------
def load_mutes():
    if os.path.exists(MUTE_FILE):
        with open(MUTE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_mutes(data):
    with open(MUTE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def parse_time(time_str):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.match(r"(\d+)([smhd])$", time_str.lower())
    if match:
        amount, unit = match.groups()
        return int(amount) * units[unit]
    return None

def format_time(seconds):
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds//60}m"
    elif seconds < 86400:
        return f"{seconds//3600}h"
    else:
        return f"{seconds//86400}d"

# -------------------------
# Mute Cog
# -------------------------
class Mute(commands.Cog):
    """Mute system with persistent storage, auto unmute, and manual unmute."""

    def __init__(self, bot):
        self.bot = bot
        self.active_mutes = load_mutes()
        self.bot.loop.create_task(self.resume_mutes())

    # -------------------------
    # Mute Command
    # -------------------------
    @commands.command(name="mute")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, duration: str, member: discord.Member, *, reason: str = "No reason provided"):
        seconds = parse_time(duration)
        if seconds is None:
            await ctx.send(embed=discord.Embed(
                title="❌ Invalid Time",
                description="Please use a valid time format: `1s`, `30m`, `1h`, `2d`",
                color=discord.Color.red()
            ))
            return

        guild = ctx.guild
        muted_role = discord.utils.get(guild.roles, name="Muted")

        if muted_role is None:
            try:
                muted_role = await guild.create_role(
                    name="Muted",
                    permissions=discord.Permissions(send_messages=False, speak=False),
                    reason="Creating Muted role"
                )
                for channel in guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
            except discord.Forbidden:
                await ctx.send(embed=discord.Embed(
                    title="❌ Missing Permissions",
                    description="Cannot create Muted role or set permissions",
                    color=discord.Color.red()
                ))
                return

        await member.add_roles(muted_role, reason=reason)
        unmute_time = int(discord.utils.utcnow().timestamp()) + seconds

        # Save to JSON
        self.active_mutes[str(member.id)] = {
            "guild_id": guild.id,
            "unmute_time": unmute_time,
            "reason": reason
        }
        save_mutes(self.active_mutes)

        # DM user
        try:
            await member.send(embed=discord.Embed(
                title="You have been muted",
                description=f"Server: {guild.name}\nReason: {reason}\nDuration: {format_time(seconds)}",
                color=discord.Color.yellow()
            ))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title="⚠️ Cannot DM",
                description=f"{member.mention} has DMs closed, cannot send mute notification.",
                color=discord.Color.yellow()
            ))

        # Notify server
        await ctx.send(embed=discord.Embed(
            title="🔇 Member Muted",
            description=f"{member.mention} has been muted for `{format_time(seconds)}`\nReason: {reason}",
            color=discord.Color.yellow()
        ))

        # Schedule unmute
        self.bot.loop.create_task(self.unmute_after(member, muted_role, seconds))

    # -------------------------
    # Automatic unmute
    # -------------------------
    async def unmute_after(self, member, role, seconds):
        await asyncio.sleep(seconds)
        await self.unmute_member(member, role, auto=True)

    async def unmute_member(self, member, role, auto=False, reason="Time Up Bud"):
        if role in member.roles:
            try:
                await member.remove_roles(role, reason=reason)
                self.active_mutes.pop(str(member.id), None)
                save_mutes(self.active_mutes)

                # DM user
                try:
                    title = "You have been unmuted"
                    embed = discord.Embed(
                        title=title,
                        description=f"Server: {member.guild.name}\nReason: {reason}\nDuration: —",
                        color=discord.Color.green()
                    )
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass

                # Notify server
                channel = member.guild.system_channel
                if channel is None:
                    for c in member.guild.text_channels:
                        if c.permissions_for(member.guild.me).send_messages:
                            channel = c
                            break

                if channel is not None:
                    desc = f"{member.mention} has been {'automatically ' if auto else ''}unmuted.\nReason: {reason}"
                    await channel.send(embed=discord.Embed(
                        title="🔊 Member Unmuted",
                        description=desc,
                        color=discord.Color.green()
                    ))
            except discord.Forbidden:
                pass

    # -------------------------
    # Manual Unmute Command
    # -------------------------
    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        guild = ctx.guild
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if muted_role is None or muted_role not in member.roles:
            await ctx.send(embed=discord.Embed(
                title="⚠️ Not Muted",
                description=f"{member.mention} is not muted.",
                color=discord.Color.orange()
            ))
            return

        # Cancel scheduled automatic unmute
        self.active_mutes.pop(str(member.id), None)
        save_mutes(self.active_mutes)

        await self.unmute_member(member, muted_role, auto=False, reason=reason)

    # -------------------------
    # Resume mutes after restart
    # -------------------------
    async def resume_mutes(self):
        await self.bot.wait_until_ready()
        now = int(discord.utils.utcnow().timestamp())
        for member_id, data in list(self.active_mutes.items()):
            guild = self.bot.get_guild(data["guild_id"])
            if not guild:
                continue
            member = guild.get_member(int(member_id))
            if not member:
                continue
            muted_role = discord.utils.get(guild.roles, name="Muted")
            if not muted_role:
                continue
            remaining = data["unmute_time"] - now
            if remaining <= 0:
                await self.unmute_member(member, muted_role)
            else:
                self.bot.loop.create_task(self.unmute_after(member, muted_role, remaining))

# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(Mute(bot))