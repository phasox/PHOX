import discord
from discord.ext import commands

class ServerList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="list")
    @commands.is_owner()
    async def list_servers(self, ctx):
        if not self.bot.guilds:
            await ctx.send("The bot is not in any servers.")
            return

        embed = discord.Embed(
            title="Servers I'm In",
            color=discord.Color.green()
        )

        for guild in self.bot.guilds:
            invite_link = "No permission to create invite."

            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    try:
                        invite = await channel.create_invite(max_age=0, max_uses=0)
                        invite_link = invite.url
                        break
                    except:
                        continue

            embed.add_field(
                name=guild.name,
                value=f"Members: {guild.member_count}\nInvite: {invite_link}",
                inline=False
            )

        await ctx.send(embed=embed)

    # ❌ Error handler
    @list_servers.error
    async def list_servers_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You are not the bot owner.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            raise error  # keep other errors normal

async def setup(bot):
    await bot.add_cog(ServerList(bot))