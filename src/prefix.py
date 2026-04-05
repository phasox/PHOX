import discord
from discord.ext import commands
import json
import os

PREFIX_FILE = "data/prefixes.json"

class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setprefix")
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx, prefix: str):
        """Change the server prefix (admin only)."""

        # Make sure the folder exists
        if not os.path.exists("data"):
            os.makedirs("data")

        # Load current prefixes
        if os.path.exists(PREFIX_FILE):
            with open(PREFIX_FILE, "r") as f:
                prefixes = json.load(f)
        else:
            prefixes = {}

        # Update the prefix for this server
        prefixes[str(ctx.guild.id)] = prefix

        # Save back to JSON
        with open(PREFIX_FILE, "w") as f:
            json.dump(prefixes, f, indent=4)

        # Create the embed
        embed = discord.Embed(
            title="✅ Prefix Changed",
            description=f"The server prefix has been updated to `{prefix}`",
            color=discord.Color.green()
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Prefix(bot))