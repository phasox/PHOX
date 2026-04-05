import discord
from discord.ext import commands
from discord import ui
import json
import os
from datetime import datetime

SNIPES_FILE = "data/snipe.json"

# -----------------------
# JSON Helpers
# -----------------------
def load_snipes():
    if os.path.exists(SNIPES_FILE):
        with open(SNIPES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_snipes(data):
    os.makedirs("data", exist_ok=True)
    with open(SNIPES_FILE, "w") as f:
        json.dump(data, f, indent=4)

# -----------------------
# View for embed navigation
# -----------------------
class SnipeView(ui.View):
    def __init__(self, snipes, user):
        super().__init__(timeout=120)
        self.snipes = snipes
        self.index = 0
        self.user = user

    def create_embed(self, data):
        embed = discord.Embed(
            title="🕵️ Deleted Message",
            description=data.get("content") or "*No message content*",
            color=discord.Color.blurple(),
            timestamp=datetime.fromtimestamp(data["deleted_at"])
        )
        embed.set_author(
            name=f"{data['author_name']} ({data['author_id']})",
            icon_url=data["avatar_url"]
        )
        embed.add_field(
            name="Deleted At",
            value=f"<t:{data['deleted_at']}:F>",
            inline=False
        )

        attachments = data.get("attachments", [])
        files_text = []
        for att in attachments:
            if att.get("is_image"):
                embed.set_image(url=att["url"])
            else:
                files_text.append(f"[{att['filename']}]({att['url']})")
        if files_text:
            embed.add_field(name="Attachments", value="\n".join(files_text), inline=False)

        embed.set_footer(text=f"Snipe {self.index+1}/{len(self.snipes)}")
        return embed

    async def update(self, interaction):
        embed = self.create_embed(self.snipes[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="⬅ Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("You can't control this menu.", ephemeral=True)
        self.index = (self.index - 1) % len(self.snipes)
        await self.update(interaction)

    @ui.button(label="Next ➡", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("You can't control this menu.", ephemeral=True)
        self.index = (self.index + 1) % len(self.snipes)
        await self.update(interaction)

# -----------------------
# Main Cog
# -----------------------
class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes = load_snipes()

    # -----------------------
    # Listener
    # -----------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        if guild_id not in self.snipes:
            self.snipes[guild_id] = {}
        if channel_id not in self.snipes[guild_id]:
            self.snipes[guild_id][channel_id] = []

        attachments = [
            {
                "url": att.url,
                "filename": att.filename,
                "is_image": att.content_type and att.content_type.startswith("image")
            }
            for att in message.attachments
        ]

        # Add deleted message to the front
        self.snipes[guild_id][channel_id].insert(0, {
            "author_id": message.author.id,
            "author_name": str(message.author),
            "avatar_url": message.author.display_avatar.url,
            "content": message.content,
            "attachments": attachments,
            "deleted_at": int(datetime.utcnow().timestamp())
        })

        # Keep only the last 25 messages
        self.snipes[guild_id][channel_id] = self.snipes[guild_id][channel_id][:25]
        save_snipes(self.snipes)

    # -----------------------
    # DM Snipe Command
    # -----------------------
    @commands.command()
    async def snipe(self, ctx):
        guild_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)

        if guild_id not in self.snipes or channel_id not in self.snipes[guild_id]:
            return await ctx.send("❌ No deleted messages found in this channel.", delete_after=5)

        snipes_list = self.snipes[guild_id][channel_id]
        view = SnipeView(snipes_list, ctx.author)
        embed = view.create_embed(snipes_list[0])

        try:
            await ctx.author.send(embed=embed, view=view)
            await ctx.send("📩 I've sent you the deleted messages via DM.", delete_after=5)
        except discord.Forbidden:
            await ctx.send("⚠️ I couldn't DM you. Do you have DMs disabled?", delete_after=5)

# -----------------------
# Setup
# -----------------------
async def setup(bot):
    await bot.add_cog(Snipe(bot))