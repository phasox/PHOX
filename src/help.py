import discord
from discord.ext import commands
from discord import ui
from config.prefix import DEFAULT_PREFIX
import json
import os
from typing import Optional

PREFIX_FILE = "data/prefixes.json"

PHOX_MAIN = 0x7D4DFF
PHOX_DARK = 0x2B1847


# -------------------------
# Prefix Helpers
# -------------------------
def get_server_prefix(guild_id: Optional[int]) -> str:
    if guild_id is None:
        return DEFAULT_PREFIX

    if not os.path.exists(PREFIX_FILE):
        return DEFAULT_PREFIX

    try:
        with open(PREFIX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return DEFAULT_PREFIX
    except (json.JSONDecodeError, OSError):
        return DEFAULT_PREFIX

    return data.get(str(guild_id), DEFAULT_PREFIX)


# -------------------------
# Command Categories
# -------------------------
CUSTOM_COMMANDS = {
    "General": {
        "emoji": "🏠",
        "commands": [
            {"name": "ping", "usage": "ping", "description": "Check bot latency."},
            {"name": "help", "usage": "help", "description": "Show the help menu."}
        ]
    },
    "Config": {
        "emoji": "⚙️",
        "commands": [
            {"name": "setprefix", "usage": "setprefix <prefix>", "description": "Change the server prefix."},
            {"name": "setlog", "usage": "setlog <#channel>", "description": "Set the log channel."},
            {"name": "setwelcome", "usage": "setwelcome <#channel>", "description": "Set the welcome channel."},
            {"name": "setleave", "usage": "setleave <#channel>", "description": "Set the leave channel."},
            {"name": "setautorole", "usage": "setautorole <role>", "description": "Set the autorole."}
        ]
    },
    "Moderation": {
        "emoji": "🛡️",
        "commands": [
            {"name": "nuke", "usage": "nuke", "description": "Nuke the current channel safely."},
            {"name": "mute", "usage": "mute <time> <@user> <reason>", "description": "Mute a user."},
            {"name": "unmute", "usage": "unmute <@user> <reason>", "description": "Manually unmute a member."},
            {"name": "warn", "usage": "warn <@user>", "description": "Warn a user and save it."},
            {"name": "warnings", "usage": "warnings <@user>", "description": "Check a user's warnings."},
            {"name": "clearwarns", "usage": "clearwarns <@user>", "description": "Clear a user's warnings."}
        ]
    },
    "Admin": {
        "emoji": "👑",
        "commands": [
            {"name": "kick", "usage": "kick <@user> <reason>", "description": "Kick a member from the server."},
            {"name": "ban", "usage": "ban <@user> <reason>", "description": "Ban a member from the server."},
            {"name": "serverban", "usage": "serverban <user_id> <reason>", "description": "Ban a user by ID."},
            {"name": "forcekick", "usage": "forcekick <user_id> <reason>", "description": "Kick a user by ID."},
            {"name": "unban", "usage": "unban <user_id>", "description": "Unban a user by ID."},
            {"name": "lock", "usage": "lock", "description": "Lock the current channel."},
            {"name": "unlock", "usage": "unlock", "description": "Unlock the current channel."},
            {"name": "slowmode", "usage": "slowmode <seconds>", "description": "Set slowmode for the channel."},
            {"name": "purge", "usage": "purge <amount>", "description": "Delete messages."}
        ]
    },
    "Economy": {
        "emoji": "💰",
        "commands": [
            {"name": "balance", "usage": "balance", "description": "Check your coin balance."},
            {"name": "daily", "usage": "daily", "description": "Claim your daily PhaseCoins reward."},
            {"name": "work", "usage": "work", "description": "Earn random PhaseCoins."},
            {"name": "shop", "usage": "shop", "description": "View the server shop."},
            {"name": "buy", "usage": "buy <item>", "description": "Buy an item from the shop."}
        ]
    },
    "Ticket": {
        "emoji": "🎫",
        "commands": [
            {"name": "ticket_setup", "usage": "ticket_setup <@role> <#log>", "description": "Setup the ticket system."},
            {"name": "ticket_panel", "usage": "ticket_panel", "description": "Send the create-ticket panel."},
            {"name": "close", "usage": "close", "description": "Delete the current ticket and save transcript."},
            {"name": "add", "usage": "add <@user>", "description": "Add a user to the ticket."},
            {"name": "remove", "usage": "remove <@user>", "description": "Remove a user from the ticket."}
        ]
    },
    "Verify": {
        "emoji": "✅",
        "commands": [
            {"name": "verify_setup", "usage": "verify_setup <@role> <#log>", "description": "Set the verify role and log channel."},
            {"name": "verify_panel", "usage": "verify_panel", "description": "Show the verify panel."}
        ]
    },
    "Antinuke": {
        "emoji": "💥",
        "commands": [
            {"name": "antinuke", "usage": "antinuke", "description": "Show anti-nuke status."},
            {"name": "antinuke_on", "usage": "antinuke on", "description": "Enable anti-nuke protection."},
            {"name": "antinuke_off", "usage": "antinuke off", "description": "Disable anti-nuke protection."},
            {"name": "antinuke_setup", "usage": "antinuke setup <#log> [threshold] [window] [punishment]", "description": "Configure anti-nuke settings."},
            {"name": "antinuke_whitelist_add", "usage": "antinuke whitelist add <@user/@role>", "description": "Whitelist a user or role from anti-nuke."},
            {"name": "antinuke_whitelist_remove", "usage": "antinuke whitelist remove <@user/@role>", "description": "Remove an anti-nuke whitelist entry."},
            {"name": "antinuke_whitelist_list", "usage": "antinuke whitelist list", "description": "Show anti-nuke whitelist entries."}
        ]
    },
    "Antiraid": {
        "emoji": "🚨",
        "commands": [
            {"name": "antiraid", "usage": "antiraid", "description": "Show anti-raid status."},
            {"name": "antiraid_on", "usage": "antiraid on", "description": "Enable anti-raid protection."},
            {"name": "antiraid_off", "usage": "antiraid off", "description": "Disable anti-raid protection."},
            {"name": "antiraid_setup", "usage": "antiraid setup <#log> [joins] [window] [age] [punishment]", "description": "Configure anti-raid settings."},
            {"name": "antiraid_joins", "usage": "antiraid joins <count> [window]", "description": "Set the join-flood trigger."},
            {"name": "antiraid_mentions", "usage": "antiraid mentions <count>", "description": "Set the mass-mention trigger."},
            {"name": "antiraid_spam", "usage": "antiraid spam <count> [window]", "description": "Set the spam trigger."},
            {"name": "antiraid_accountage", "usage": "antiraid accountage <minutes>", "description": "Set the minimum account age."},
            {"name": "antiraid_punishment", "usage": "antiraid punishment <ban/kick/timeout>", "description": "Choose the anti-raid punishment."},
            {"name": "antiraid_whitelist_add", "usage": "antiraid whitelist add <@user/@role>", "description": "Whitelist a user or role from anti-raid."},
            {"name": "antiraid_whitelist_remove", "usage": "antiraid whitelist remove <@user/@role>", "description": "Remove an anti-raid whitelist entry."},
            {"name": "antiraid_whitelist_list", "usage": "antiraid whitelist list", "description": "Show anti-raid whitelist entries."}
        ]
    },
    "AFK": {
        "emoji": "🌙",
        "commands": [
            {"name": "afk", "usage": "afk [reason]", "description": "Set yourself as AFK."}
        ]
    }
}


# -------------------------
# Embed Builders
# -------------------------
def build_home_embed(prefix: str) -> discord.Embed:
    embed = discord.Embed(
        title="🌌 PHOX Help Menu",
        description=(
            "Click a **category button** below.\n"
            "Then use the **dropdown** to pick a command and see how it works.\n\n"
            f"**Current Prefix:** `{prefix}`"
        ),
        color=PHOX_MAIN
    )

    value = []
    for category, data in CUSTOM_COMMANDS.items():
        value.append(f"{data['emoji']} **{category}**")

    embed.add_field(
        name="Available Categories",
        value="\n".join(value),
        inline=False
    )

    embed.set_footer(text="PHOX • Made by PhaseDev")
    return embed


def build_category_embed(category: str, prefix: str) -> discord.Embed:
    data = CUSTOM_COMMANDS.get(category, {})
    commands_list = data.get("commands", [])
    emoji = data.get("emoji", "📂")

    embed = discord.Embed(
        title=f"{emoji} {category} Commands",
        description=f"Select a command from the dropdown below.\n**Prefix:** `{prefix}`",
        color=PHOX_MAIN
    )

    preview = []
    for cmd in commands_list[:15]:
        preview.append(f"• `{prefix}{cmd['usage']}`")

    embed.add_field(
        name="Commands",
        value="\n".join(preview) if preview else "No commands found.",
        inline=False
    )

    embed.set_footer(text=f"{len(commands_list)} command(s) in {category}")
    return embed


def build_command_embed(category: str, command_data: dict, prefix: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚡ Command: {command_data['name']}",
        description=command_data["description"],
        color=PHOX_MAIN
    )

    embed.add_field(
        name="Usage",
        value=f"`{prefix}{command_data['usage']}`",
        inline=False
    )

    embed.add_field(
        name="How it works",
        value=(
            f"Use `{prefix}{command_data['usage']}` in chat.\n"
            f"This command will: **{command_data['description']}**"
        ),
        inline=False
    )

    embed.add_field(name="Category", value=category, inline=True)
    embed.add_field(name="Prefix", value=f"`{prefix}`", inline=True)

    embed.set_footer(text="PHOX Command Guide")
    return embed


# -------------------------
# Dropdown
# -------------------------
class CommandDropdown(ui.Select):
    def __init__(self, author_id: int, category: str):
        self.author_id = author_id
        self.category = category
        self.commands_data = CUSTOM_COMMANDS.get(category, {}).get("commands", [])

        options = [
            discord.SelectOption(
                label=cmd["name"][:100],
                description=cmd["description"][:100],
                emoji="⚡"
            )
            for cmd in self.commands_data[:25]
        ]

        super().__init__(
            placeholder=f"Select a command from {category}...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ You cannot use someone else's help menu.",
                ephemeral=True
            )
            return

        selected = self.values[0]
        prefix = get_server_prefix(interaction.guild.id if interaction.guild else None)

        command_data = None
        for cmd in self.commands_data:
            if cmd["name"] == selected:
                command_data = cmd
                break

        if not command_data:
            await interaction.response.send_message("❌ Command not found.", ephemeral=True)
            return

        embed = build_command_embed(self.category, command_data, prefix)

        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.response.edit_message(embed=embed, view=self.view)


# -------------------------
# Buttons
# -------------------------
class CategoryButton(ui.Button):
    def __init__(self, author_id: int, category: str, emoji: str):
        self.author_id = author_id
        self.category = category

        super().__init__(
            label=category[:80],
            emoji=emoji,
            style=discord.ButtonStyle.primary
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This help menu is not for you.",
                ephemeral=True
            )
            return

        prefix = get_server_prefix(interaction.guild.id if interaction.guild else None)
        embed = build_category_embed(self.category, prefix)

        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        view = CategoryView(self.author_id, self.category)
        view.message = interaction.message
        await interaction.response.edit_message(embed=embed, view=view)


class HomeButton(ui.Button):
    def __init__(self, author_id: int):
        self.author_id = author_id
        super().__init__(label="Home", emoji="🏠", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This help menu is not for you.",
                ephemeral=True
            )
            return

        prefix = get_server_prefix(interaction.guild.id if interaction.guild else None)
        embed = build_home_embed(prefix)

        if interaction.guild:
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_author(name=interaction.guild.name)

        view = HelpView(self.author_id)
        view.message = interaction.message
        await interaction.response.edit_message(embed=embed, view=view)


# -------------------------
# Views
# -------------------------
class HelpView(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.message = None

        for category, data in list(CUSTOM_COMMANDS.items())[:20]:
            self.add_item(CategoryButton(author_id, category, data["emoji"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This help menu is not for you.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class CategoryView(ui.View):
    def __init__(self, author_id: int, category: str):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.category = category
        self.message = None

        self.add_item(CommandDropdown(author_id, category))
        self.add_item(HomeButton(author_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This help menu is not for you.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# -------------------------
# Help Cog
# -------------------------
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx):
        prefix = get_server_prefix(ctx.guild.id if ctx.guild else None)
        embed = build_home_embed(prefix)

        if ctx.guild:
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            embed.set_author(name=ctx.guild.name)

        view = HelpView(ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        view.message = message


# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(Help(bot))