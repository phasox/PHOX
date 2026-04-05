import discord
from discord.ext import commands
import asyncio
import json
import os

ADMIN_FILE = "data/admin.json"

def load_data():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "r") as f:
            return json.load(f)
    return {"warnings": {}, "mutes": {}}

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(ADMIN_FILE, "w") as f:
        json.dump(data, f, indent=4)

class Admin(commands.Cog):
    """Admin commands with embed notifications and JSON storage"""

    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()


    # -----------------------
    # DM COMMANDS
    # -----------------------
    @commands.command(name="dm")
    @commands.has_permissions(administrator=True)
    async def dm(self, ctx, member: discord.Member, *, message: str):
        try:
            dm_embed = discord.Embed(title="📩 DM from Admin", description=message, color=discord.Color.gold())
            await member.send(embed=dm_embed)
            await ctx.send(embed=discord.Embed(title="✅ DM Sent", description=f"Message sent to {member.mention}", color=discord.Color.green()))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(title="⚠️ Cannot DM", description="User has DMs blocked.", color=discord.Color.orange()))

    @commands.command(name="dmall")
    @commands.has_permissions(administrator=True)
    async def dmall(self, ctx, *, message: str):
        success = 0
        failed = 0
        await ctx.send(embed=discord.Embed(title="📨 Sending DMs...", description="Please wait...", color=discord.Color.blurple()))
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                dm_embed = discord.Embed(title="📩 DM from Admin", description=message, color=discord.Color.gold())
                await member.send(embed=dm_embed)
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1
            await asyncio.sleep(0.1)
        embed = discord.Embed(title="✅ DMs Sent", description=f"{success} members received the message.\n⚠️ {failed} could not be contacted.", color=discord.Color.green())
        await ctx.send(embed=embed)

    # -----------------------
    # DELETE ALL CHANNELS (Server Owner Only)
    # -----------------------
    @commands.command(name="delchannels")
    async def delete_channels(self, ctx):
        if ctx.author != ctx.guild.owner:
            embed = discord.Embed(title="❌ Permission Denied", description="Only the server owner can use this command.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return
        await ctx.send(embed=discord.Embed(title="⚠️ Deleting Channels", description="Deleting all channels...", color=discord.Color.orange()))
        for channel in ctx.guild.channels:
            try:
                await channel.delete()
            except Exception:
                pass

    @commands.command(name="forcenick")
    @commands.has_permissions(manage_nicknames=True)
    async def forcenick(self, ctx, member: discord.Member, *, nickname: str):
        """Force change a member's nickname (admin only)."""
        try:
            await member.edit(nick=nickname)
            await ctx.send(embed=discord.Embed(
                title="✏️ Nickname Changed",
                description=f"{member.mention}'s nickname has been forcibly changed to `{nickname}`",
                color=discord.Color.green()
            ))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to change this user's nickname.",
                color=discord.Color.red()
            ))

# -----------------------
# SETUP
# -----------------------
async def setup(bot):
    await bot.add_cog(Admin(bot))