import discord
from discord.ext import commands
import asyncio

class NukeConfirmView(discord.ui.View):
    def __init__(self, author, timeout=20):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Only the command author can confirm.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm Nuking", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.message.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.message.delete()


class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # 🔥 SINGLE CHANNEL NUKE
    # =========================
    @commands.command(name="nukev2")
    async def nuke(self, ctx):
        old_channel = ctx.channel
        author = ctx.author

        view = NukeConfirmView(author)
        await ctx.send(
            embed=discord.Embed(
                title="💥 Confirm Nuke",
                description=f"{author.mention}, nuke **#{old_channel.name}**?",
                color=discord.Color.orange()
            ),
            view=view
        )

        await view.wait()
        if not view.value:
            return

        # 🔗 SAVE WEBHOOKS
        webhooks = []
        try:
            webhooks = await old_channel.webhooks()
        except:
            pass

        # ⚡ CLONE
        new_channel = await old_channel.clone(reason=f"Nuked by {author}")
        await new_channel.edit(position=old_channel.position)

        # ❌ DELETE OLD
        await old_channel.delete()

        # 🔗 RESTORE WEBHOOKS
        for webhook in webhooks:
            try:
                await new_channel.create_webhook(
                    name=webhook.name,
                    avatar=await webhook.avatar.read() if webhook.avatar else None
                )
            except:
                pass

        # 💥 AUTO FIRST SPAM
        for _ in range(100):
            await new_channel.send("@everyone ")

        await new_channel.send(
            embed=discord.Embed(
                title="💥 Channel Nuked",
                description=f"{author.mention} destroyed this channel.",
                color=discord.Color.red()
            )
        )



async def setup(bot):
    await bot.add_cog(Nuke(bot))