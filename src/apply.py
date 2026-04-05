import json
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config.prefix import DEFAULT_PREFIX

APPLY_CONFIG_FILE = "data/apply_config.json"
PREFIX_FILE = "data/prefixes.json"


# -------------------------
# Helpers
# -------------------------
def ensure_data():
    os.makedirs("data", exist_ok=True)


def load_json(path, default):
    ensure_data()
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    ensure_data()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_server_prefix(guild_id: int | None):
    if guild_id is None:
        return DEFAULT_PREFIX

    prefixes = load_json(PREFIX_FILE, {})
    return prefixes.get(str(guild_id), DEFAULT_PREFIX)


def get_guild_config(guild_id: int):
    return load_json(APPLY_CONFIG_FILE, {}).get(str(guild_id))


def clip(text, limit):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# -------------------------
# UI
# -------------------------
class ApplyModal(discord.ui.Modal):
    def __init__(self, guild_id: int, apply_for: str, question: str):
        super().__init__(title=clip(f"Apply for {apply_for}", 45))
        self.guild_id = guild_id
        self.apply_for = apply_for
        self.question = question

        self.answer = discord.ui.TextInput(
            label=clip(question, 45),
            placeholder=clip(question, 100),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This application can only be submitted inside a server.",
                ephemeral=True,
            )
            return

        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "The application system is not configured right now.",
                ephemeral=True,
            )
            return

        review_channel_id = config.get("review_channel_id")
        review_channel = interaction.guild.get_channel(review_channel_id) if review_channel_id else None
        if review_channel is None:
            await interaction.response.send_message(
                "The review channel is missing. Ask an admin to run the setup again.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"New Application: {clip(self.apply_for, 200)}",
            description=clip(self.answer.value, 4000),
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="Applicant",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Applying For",
            value=clip(self.apply_for, 1024),
            inline=False,
        )
        embed.add_field(
            name="Question",
            value=clip(self.question, 1024),
            inline=False,
        )
        embed.set_footer(text=f"{interaction.guild.name} application")

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        try:
            await review_channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to send applications to the review channel.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "I could not send your application. Please try again later.",
                ephemeral=True,
            )
            return

        confirm = discord.Embed(
            title="Application Sent",
            description=f"Your application for **{self.apply_for}** has been submitted.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)


class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Application",
        style=discord.ButtonStyle.blurple,
        custom_id="phox_apply_open",
    )
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This button only works inside a server.",
                ephemeral=True,
            )
            return

        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "The application system is not configured yet.",
                ephemeral=True,
            )
            return

        apply_for = config.get("apply_for")
        question = config.get("question")
        if not apply_for or not question:
            await interaction.response.send_message(
                "The application setup is incomplete. Ask an admin to update it.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApplyModal(interaction.guild.id, apply_for, question)
        )


# -------------------------
# Cog
# -------------------------
class Apply(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            self.bot.add_view(ApplyView())
        except Exception:
            pass

    @commands.command(name="apply_setup")
    @commands.has_permissions(administrator=True)
    async def apply_setup(self, ctx, review_channel: discord.TextChannel, *, settings: str):
        if not ctx.guild:
            return

        if "|" not in settings:
            prefix = get_server_prefix(ctx.guild.id)
            await ctx.send(
                f"Usage: `{prefix}apply_setup #review-channel <apply for> | <question>`"
            )
            return

        apply_for, question = [part.strip() for part in settings.split("|", 1)]
        if not apply_for or not question:
            prefix = get_server_prefix(ctx.guild.id)
            await ctx.send(
                f"Usage: `{prefix}apply_setup #review-channel <apply for> | <question>`"
            )
            return

        data = load_json(APPLY_CONFIG_FILE, {})
        data[str(ctx.guild.id)] = {
            "review_channel_id": review_channel.id,
            "apply_for": apply_for,
            "question": question,
        }
        save_json(APPLY_CONFIG_FILE, data)

        embed = discord.Embed(
            title="Application Setup Complete",
            color=discord.Color.green(),
        )
        embed.add_field(name="Review Channel", value=review_channel.mention, inline=False)
        embed.add_field(name="Apply For", value=clip(apply_for, 1024), inline=False)
        embed.add_field(name="Question", value=clip(question, 1024), inline=False)
        embed.add_field(
            name="Next Step",
            value="Use `apply_panel` in the channel where users should see the application button.",
            inline=False,
        )
        embed.set_footer(text=f"Requested by {ctx.author}")

        await ctx.send(embed=embed)

    @commands.command(name="apply_panel")
    @commands.has_permissions(administrator=True)
    async def apply_panel(self, ctx):
        if not ctx.guild:
            return

        config = get_guild_config(ctx.guild.id)
        if not config:
            prefix = get_server_prefix(ctx.guild.id)
            await ctx.send(
                f"Run `{prefix}apply_setup #review-channel <apply for> | <question>` first."
            )
            return

        apply_for = config.get("apply_for")
        question = config.get("question")
        if not apply_for or not question:
            await ctx.send("The application setup is incomplete. Run the setup again.")
            return

        embed = discord.Embed(
            title="PHOX Application Center",
            description=(
                f"Applications are now open for **{clip(apply_for, 200)}**.\n"
                "Press the button below, answer the question, and staff will review your response."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Position", value=clip(apply_for, 1024), inline=False)
        embed.add_field(name="Question", value=clip(question, 1024), inline=False)
        embed.add_field(
            name="How It Works",
            value=(
                "1. Press **Start Application**\n"
                "2. Answer the question in the popup\n"
                "3. Wait for staff to review your application"
            ),
            inline=False,
        )
        embed.set_footer(text=f"{ctx.guild.name} applications")

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.send(embed=embed, view=ApplyView())

    @commands.command(name="apply_disable")
    @commands.has_permissions(administrator=True)
    async def apply_disable(self, ctx):
        if not ctx.guild:
            return

        data = load_json(APPLY_CONFIG_FILE, {})
        if str(ctx.guild.id) in data:
            del data[str(ctx.guild.id)]
            save_json(APPLY_CONFIG_FILE, data)

        embed = discord.Embed(
            title="Application System Disabled",
            description="Users can no longer submit applications until setup is run again.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Apply(bot))
