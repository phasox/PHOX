import discord
from discord.ext import commands
import json
import os
from config.prefix import DEFAULT_PREFIX

WARN_FILE = "data/warn.json"
WARN_EMOJI = "<:warn:1488976653710524618>"

def load_warns():
    """Load warnings from JSON file."""
    if os.path.exists(WARN_FILE):
        with open(WARN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_warns(data):
    """Save warnings to JSON file."""
    with open(WARN_FILE, "w") as f:
        json.dump(data, f, indent=4)

class Warn(commands.Cog):
    """Persistent warning system with DM notifications and custom emoji."""

    def __init__(self, bot):
        self.bot = bot
        self.warns = load_warns()

    @commands.command(name="warn")
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a user and save it."""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in self.warns:
            self.warns[guild_id] = {}
        if user_id not in self.warns[guild_id]:
            self.warns[guild_id][user_id] = []

        self.warns[guild_id][user_id].append(reason)
        save_warns(self.warns)

        count = len(self.warns[guild_id][user_id])

        # Server embed
        embed = discord.Embed(
            title=f"{WARN_EMOJI} User Warned",
            description=f"{member.mention} has been warned.\nReason: {reason}\nTotal Warnings: {count}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

        # DM embed
        try:
            dm_embed = discord.Embed(
                title=f"{WARN_EMOJI} You have been warned",
                description=f"Server: {ctx.guild.name}\nReason: {reason}\nTotal Warnings: {count}",
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title=f"{WARN_EMOJI} Cannot DM",
                description=f"{member.mention} has DMs closed, cannot send warning notification.",
                color=discord.Color.orange()
            ))

    @commands.command(name="warnings")
    @commands.has_permissions(kick_members=True)
    async def warnings(self, ctx, member: discord.Member):
        """Check a user's warnings."""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        count = len(self.warns.get(guild_id, {}).get(user_id, []))
        reasons = self.warns.get(guild_id, {}).get(user_id, [])

        embed = discord.Embed(
            title=f"{WARN_EMOJI} Warnings for {member}",
            description=f"Total Warnings: {count}",
            color=discord.Color.blue()
        )

        if reasons:
            embed.add_field(name="Reasons", value="\n".join(reasons), inline=False)
        else:
            embed.add_field(name="Reasons", value="No warnings", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="clearwarns")
    @commands.has_permissions(kick_members=True)
    async def clearwarns(self, ctx, member: discord.Member):
        """Clear a user's warnings."""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id in self.warns and user_id in self.warns[guild_id]:
            self.warns[guild_id].pop(user_id)
            save_warns(self.warns)
            await ctx.send(embed=discord.Embed(
                title=f"✅ Warnings Cleared",
                description=f"All warnings for {member.mention} have been cleared.",
                color=discord.Color.green()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title=f"{WARN_EMOJI} No Warnings",
                description=f"{member.mention} has no warnings.",
                color=discord.Color.orange()
            ))

async def setup(bot):
    await bot.add_cog(Warn(bot))