import discord
from discord.ext import commands
from discord import app_commands
import json
import os

BLACKLIST_FILE = "data/blacklist.json"

def load_blacklist():
    if not os.path.exists("data"):
        os.makedirs("data")
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f:
            return json.load(f)
    else:
        return {"users": [], "servers": []}

def save_blacklist(data):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(data, f, indent=4)

class GlobalBlacklist(commands.Cog):
    """Global Blacklist system using JSON with embed messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.blacklist = load_blacklist()
        bot.add_check(self.global_check)

    # -------------------------
    # Global Check for Commands
    # -------------------------
    async def global_check(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id if ctx.guild else None

        if user_id in self.blacklist.get("users", []):
            embed = discord.Embed(
                title="<:bl:1488978763642572960> Blacklisted",
                description="You are blacklisted and cannot use commands!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False

        if guild_id and guild_id in self.blacklist.get("servers", []):
            embed = discord.Embed(
                title="<:bl:1488978763642572960> Server Blacklisted",
                description="This server is blacklisted and cannot use commands!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False

        return True

    # -------------------------
    # Slash / Interaction Check
    # -------------------------
    async def cog_before_invoke(self, ctx_or_interaction):
        if isinstance(ctx_or_interaction, discord.Interaction):
            user_id = ctx_or_interaction.user.id
            guild_id = ctx_or_interaction.guild.id if ctx_or_interaction.guild else None

            if user_id in self.blacklist.get("users", []):
                await ctx_or_interaction.response.send_message(
                    "<:bl:1488978763642572960> You are blacklisted and cannot use commands!", ephemeral=True
                )
                raise app_commands.CheckFailure("User is blacklisted")

            if guild_id and guild_id in self.blacklist.get("servers", []):
                await ctx_or_interaction.response.send_message(
                    "<:bl:1488978763642572960> This server is blacklisted and cannot use commands!", ephemeral=True
                )
                raise app_commands.CheckFailure("Server is blacklisted")

    # -------------------------
    # Owner Commands: Users
    # -------------------------
    @commands.command(name="blacklist_user")
    @commands.is_owner()
    async def blacklist_user(self, ctx, user: discord.User):
        if user.id not in self.blacklist["users"]:
            self.blacklist["users"].append(user.id)
            save_blacklist(self.blacklist)

        embed = discord.Embed(
            title="<:bl:1488978763642572960> User Blacklisted",
            description=f"{user.mention} has been added to the global blacklist.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="unblacklist_user")
    @commands.is_owner()
    async def unblacklist_user(self, ctx, user: discord.User):
        if user.id in self.blacklist["users"]:
            self.blacklist["users"].remove(user.id)
            save_blacklist(self.blacklist)

        embed = discord.Embed(
            title="<:bl:1488978763642572960> User Removed",
            description=f"{user.mention} has been removed from the global blacklist.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="list_blacklisted_users")
    @commands.is_owner()
    async def list_blacklisted_users(self, ctx):
        users = self.blacklist.get("users", [])
        if not users:
            embed = discord.Embed(
                title="⚠️ No Blacklisted Users",
                description="There are currently no users blacklisted.",
                color=discord.Color.orange()
            )
        else:
            lines = []
            for user_id in users:
                user = self.bot.get_user(user_id)
                lines.append(f"{user} ({user_id})" if user else str(user_id))
            embed = discord.Embed(
                title="<:bl:1488978763642572960> Blacklisted Users",
                description="\n".join(lines),
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)

    # -------------------------
    # Owner Commands: Servers
    # -------------------------
    @commands.command(name="blacklist_server")
    @commands.is_owner()
    async def blacklist_server(self, ctx, guild_id: int):
        if guild_id not in self.blacklist["servers"]:
            self.blacklist["servers"].append(guild_id)
            save_blacklist(self.blacklist)

        embed = discord.Embed(
            title="<:bl:1488978763642572960> Server Blacklisted",
            description=f"Server ID `{guild_id}` has been blacklisted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="unblacklist_server")
    @commands.is_owner()
    async def unblacklist_server(self, ctx, guild_id: int):
        if guild_id in self.blacklist["servers"]:
            self.blacklist["servers"].remove(guild_id)
            save_blacklist(self.blacklist)

        embed = discord.Embed(
            title="<:bl:1488978763642572960> Server Removed",
            description=f"Server ID `{guild_id}` has been removed from the global blacklist.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="list_blacklisted_servers")
    @commands.is_owner()
    async def list_blacklisted_servers(self, ctx):
        servers = self.blacklist.get("servers", [])
        if not servers:
            embed = discord.Embed(
                title="⚠️ No Blacklisted Servers",
                description="There are currently no servers blacklisted.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="<:bl:1488978763642572960> Blacklisted Servers",
                description="\n".join(str(s) for s in servers),
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GlobalBlacklist(bot))