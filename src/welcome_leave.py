import discord
from discord.ext import commands
import json
import os

CONFIG_FILE = "data/config.json"


# -------------------------
# JSON
# -------------------------
def ensure_data():
    os.makedirs("data", exist_ok=True)


def load_config():
    ensure_data()
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# -------------------------
# Cog
# -------------------------
class WelcomeLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------
    # JOIN
    # -------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = load_config()
        gid = str(member.guild.id)

        if gid not in data:
            return

        config = data[gid]

        # Autorole
        role_id = config.get("autorole")
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Autorole system")
                except:
                    pass

        # Welcome
        channel_id = config.get("welcome_channel")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="👋 Welcome!",
                    description=f"Welcome {member.mention} to **{member.guild.name}**!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    # -------------------------
    # LEAVE
    # -------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        data = load_config()
        gid = str(member.guild.id)

        if gid not in data:
            return

        config = data[gid]

        channel_id = config.get("leave_channel")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="👋 Member Left",
                    description=f"{member} has left the server.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)


# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))