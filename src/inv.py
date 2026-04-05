import discord
from discord.ext import commands

class InviteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="invite-bot")
    async def invite_bot(self, ctx: commands.Context):
        """Sends the bot's invite link via DM in an embed."""
        invite_link = "http://phasebot.phasedev.site"

        embed = discord.Embed(
            title="🤖 Invite Me!",
            description=f"Click [here]({invite_link}) to invite the bot to your server.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="PhaseBot Invite")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        try:
            await ctx.author.send(embed=embed)
            await ctx.send(f"{ctx.author.mention}, I've sent you the invite link in DMs!")
        except discord.Forbidden:
            await ctx.send(f"{ctx.author.mention}, I couldn't DM you. Please check your privacy settings.")

# Async setup function for discord.py v2.x
async def setup(bot: commands.Bot):
    await bot.add_cog(InviteCog(bot))