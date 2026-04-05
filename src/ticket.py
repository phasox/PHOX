import discord
from discord.ext import commands
from discord import ui
from config.prefix import DEFAULT_PREFIX
import json
import os
import random
import string
from datetime import datetime, timezone

TICKET_CONFIG_FILE = "data/tickets.json"
PREFIX_FILE = "data/prefixes.json"
TRANSCRIPTS_FOLDER = "data/transcripts"


# -------------------------
# Helpers
# -------------------------
def ensure_folders():
    os.makedirs("data", exist_ok=True)
    os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)


def load_json(path, default):
    ensure_folders()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    ensure_folders()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_server_prefix(guild_id: int | None):
    if guild_id is None:
        return DEFAULT_PREFIX
    prefixes = load_json(PREFIX_FILE, {})
    return prefixes.get(str(guild_id), DEFAULT_PREFIX)


def load_ticket_data():
    data = load_json(TICKET_CONFIG_FILE, {})
    for guild_id in data:
        data[guild_id].setdefault("category_id", None)
        data[guild_id].setdefault("support_role_id", None)
        data[guild_id].setdefault("log_channel_id", None)
        data[guild_id].setdefault("counter", 1)
        data[guild_id].setdefault("tickets", {})
    return data


def save_ticket_data(data):
    save_json(TICKET_CONFIG_FILE, data)


def generate_ticket_custom_id(counter: int):
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"PHASE-{counter:04d}-{rand_part}"


def get_ticket_owner_id_from_topic(topic: str | None):
    if not topic:
        return None

    parts = [p.strip() for p in topic.split("|")]
    for part in parts:
        if part.startswith("ticket_owner:"):
            try:
                return int(part.split(":", 1)[1])
            except Exception:
                return None
    return None


def get_ticket_custom_id_from_topic(topic: str | None):
    if not topic:
        return None

    parts = [p.strip() for p in topic.split("|")]
    for part in parts:
        if part.startswith("ticket_id:"):
            return part.split(":", 1)[1]
    return None


def is_ticket_channel(channel: discord.TextChannel):
    if not isinstance(channel, discord.TextChannel):
        return False

    owner_id = get_ticket_owner_id_from_topic(channel.topic)
    ticket_id = get_ticket_custom_id_from_topic(channel.topic)
    return owner_id is not None and ticket_id is not None


async def user_has_open_ticket(guild: discord.Guild, user_id: int):
    for channel in guild.text_channels:
        if is_ticket_channel(channel):
            owner_id = get_ticket_owner_id_from_topic(channel.topic)
            if owner_id == user_id:
                return channel
    return None


async def create_transcript_file(channel: discord.TextChannel, ticket_custom_id: str):
    ensure_folders()

    safe_name = "".join(c for c in channel.name if c.isalnum() or c in ("-", "_")).rstrip()
    filename = f"{safe_name}_{ticket_custom_id}.txt"
    filepath = os.path.join(TRANSCRIPTS_FOLDER, filename)

    lines = []
    lines.append(f"Transcript for #{channel.name}")
    lines.append(f"Ticket ID: {ticket_custom_id}")
    lines.append(f"Guild: {channel.guild.name} ({channel.guild.id})")
    lines.append(f"Channel ID: {channel.id}")
    lines.append(f"Exported at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("-" * 80)

    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append(message)

    for message in messages:
        created = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author} ({message.author.id})"
        content = message.content if message.content else ""

        lines.append(f"[{created}] {author}: {content}")

        if message.attachments:
            for attachment in message.attachments:
                lines.append(f"    [Attachment] {attachment.url}")

        if message.embeds:
            lines.append(f"    [Embeds] {len(message.embeds)} embed(s)")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


async def can_manage_ticket(guild: discord.Guild, member: discord.Member, channel: discord.TextChannel):
    if not is_ticket_channel(channel):
        return False

    data = load_ticket_data()
    guild_id = str(guild.id)

    if guild_id not in data:
        return False

    config = data[guild_id]
    owner_id = get_ticket_owner_id_from_topic(channel.topic)
    support_role_id = config.get("support_role_id")
    support_role = guild.get_role(support_role_id) if support_role_id else None

    if member.guild_permissions.administrator:
        return True

    if owner_id == member.id:
        return True

    if support_role and support_role in member.roles:
        return True

    return False


async def close_ticket_and_send_transcript(guild: discord.Guild, channel: discord.TextChannel, closed_by: discord.Member | discord.User):
    if not is_ticket_channel(channel):
        return False

    data = load_ticket_data()
    guild_id = str(guild.id)

    if guild_id not in data:
        return False

    config = data[guild_id]
    ticket_custom_id = get_ticket_custom_id_from_topic(channel.topic) or "UNKNOWN"
    owner_id = get_ticket_owner_id_from_topic(channel.topic)

    filepath = await create_transcript_file(channel, ticket_custom_id)

    # DM the ticket owner
    owner = guild.get_member(owner_id)
    if owner is None and owner_id is not None:
        try:
            owner = await guild.fetch_member(owner_id)
        except Exception:
            owner = None

    if owner:
        try:
            dm_embed = discord.Embed(
                title="📁 Your Ticket Has Been Closed",
                description=(
                    f"**Ticket ID:** `{ticket_custom_id}`\n"
                    f"**Server:** {guild.name}\n"
                    f"**Closed by:** {closed_by.mention if hasattr(closed_by, 'mention') else closed_by}\n\n"
                    "Here is your ticket transcript."
                ),
                color=discord.Color.blurple()
            )
            await owner.send(embed=dm_embed, file=discord.File(filepath))
        except discord.Forbidden:
            pass
        except Exception:
            pass

    # Log channel
    log_channel_id = config.get("log_channel_id")
    log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

    if log_channel:
        embed = discord.Embed(
            title="📁 Ticket Closed",
            description=(
                f"**Ticket ID:** `{ticket_custom_id}`\n"
                f"**Channel:** `{channel.name}`\n"
                f"**Closed by:** {closed_by.mention if hasattr(closed_by, 'mention') else closed_by}\n"
                f"**Owner ID:** `{owner_id}`"
            ),
            color=discord.Color.red()
        )
        try:
            await log_channel.send(embed=embed, file=discord.File(filepath))
        except discord.HTTPException:
            await log_channel.send(embed=embed)

    # Remove saved ticket data
    if str(channel.id) in config.get("tickets", {}):
        del config["tickets"][str(channel.id)]
        data[guild_id] = config
        save_ticket_data(data)

    try:
        await channel.delete(reason=f"Ticket closed by {closed_by}")
    except discord.Forbidden:
        return False

    return True


# -------------------------
# Views
# -------------------------
class TicketPanelView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(
        label="🎫 Create Ticket",
        style=discord.ButtonStyle.green,
        custom_id="phase_ticket_create"
    )
    async def create_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("❌ This only works in a server.", ephemeral=True)
            return

        guild = interaction.guild
        user = interaction.user
        data = load_ticket_data()
        guild_id = str(guild.id)

        if guild_id not in data:
            await interaction.response.send_message("❌ Ticket system is not set up.", ephemeral=True)
            return

        config = data[guild_id]
        category_id = config.get("category_id")
        support_role_id = config.get("support_role_id")
        log_channel_id = config.get("log_channel_id")
        counter = config.get("counter", 1)

        category = guild.get_channel(category_id) if category_id else None
        support_role = guild.get_role(support_role_id) if support_role_id else None
        log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

        existing = await user_has_open_ticket(guild, user.id)
        if existing:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True
            )
            return

        ticket_custom_id = generate_ticket_custom_id(counter)
        channel_name = f"ticket-{counter}"

        bot_member = guild.me or guild.get_member(self.bot.user.id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
        }

        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{user.id} | ticket_id:{ticket_custom_id}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I do not have permission to create ticket channels.",
                ephemeral=True
            )
            return

        config["counter"] = counter + 1
        config["tickets"][str(ticket_channel.id)] = {
            "ticket_custom_id": ticket_custom_id,
            "owner_id": user.id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        data[guild_id] = config
        save_ticket_data(data)

        embed = discord.Embed(
            title="🎫 Ticket Created",
            description=(
                f"Hello {user.mention}, your ticket is now open.\n\n"
                f"**Ticket ID:** `{ticket_custom_id}`\n"
                "Please explain your issue and wait for staff."
            ),
            color=discord.Color.green()
        )

        if support_role:
            embed.add_field(name="Support Role", value=support_role.mention, inline=False)

        embed.set_footer(text=f"User ID: {user.id}")

        content = user.mention
        if support_role:
            content += f" {support_role.mention}"

        await ticket_channel.send(
            content=content,
            embed=embed,
            view=TicketControlView(self.bot)
        )

        if log_channel:
            log_embed = discord.Embed(
                title="📂 Ticket Opened",
                description=(
                    f"**User:** {user.mention}\n"
                    f"**Channel:** {ticket_channel.mention}\n"
                    f"**Ticket ID:** `{ticket_custom_id}`"
                ),
                color=discord.Color.blurple()
            )
            await log_channel.send(embed=log_embed)

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True
        )


class DeleteTicketConfirmView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @ui.button(label="✅ Delete Ticket", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Invalid channel.", ephemeral=True)
            return

        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if not await can_manage_ticket(interaction.guild, interaction.user, interaction.channel):
            await interaction.response.send_message("❌ You cannot delete this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ Deleting ticket and saving transcript...", ephemeral=True)
        await close_ticket_and_send_transcript(interaction.guild, interaction.channel, interaction.user)

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="❌ Ticket deletion cancelled.", embed=None, view=None)


class TicketControlView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(
        label="🗑️ Delete Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="phase_ticket_delete"
    )
    async def delete_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Invalid channel.", ephemeral=True)
            return

        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if not await can_manage_ticket(interaction.guild, interaction.user, interaction.channel):
            await interaction.response.send_message("❌ You cannot delete this ticket.", ephemeral=True)
            return

        ticket_id = get_ticket_custom_id_from_topic(interaction.channel.topic)
        embed = discord.Embed(
            title="⚠️ Confirm Ticket Deletion",
            description=f"Are you sure you want to delete ticket `{ticket_id}`?\nA transcript will be saved first.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=DeleteTicketConfirmView(self.bot), ephemeral=True)

    @ui.button(
        label="📄 Transcript",
        style=discord.ButtonStyle.blurple,
        custom_id="phase_ticket_transcript"
    )
    async def transcript_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Invalid channel.", ephemeral=True)
            return

        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if not await can_manage_ticket(interaction.guild, interaction.user, interaction.channel):
            await interaction.response.send_message("❌ You cannot export this transcript.", ephemeral=True)
            return

        ticket_id = get_ticket_custom_id_from_topic(interaction.channel.topic) or "UNKNOWN"
        filepath = await create_transcript_file(interaction.channel, ticket_id)

        try:
            await interaction.response.send_message(
                content=f"✅ Transcript for `{ticket_id}`",
                file=discord.File(filepath),
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.response.send_message("❌ Failed to send transcript.", ephemeral=True)


# -------------------------
# Cog
# -------------------------
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.bot.add_view(TicketPanelView(self.bot))
        except Exception:
            pass

        try:
            self.bot.add_view(TicketControlView(self.bot))
        except Exception:
            pass

    @commands.command(name="ticket_setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx, support_role: discord.Role, log_channel: discord.TextChannel):
        if not ctx.guild:
            return

        guild = ctx.guild
        data = load_ticket_data()
        guild_id = str(guild.id)

        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            try:
                category = await guild.create_category("Tickets")
            except discord.Forbidden:
                await ctx.send("❌ I do not have permission to create the ticket category.")
                return

        old_counter = data.get(guild_id, {}).get("counter", 1)
        old_tickets = data.get(guild_id, {}).get("tickets", {})

        data[guild_id] = {
            "category_id": category.id,
            "support_role_id": support_role.id,
            "log_channel_id": log_channel.id,
            "counter": old_counter,
            "tickets": old_tickets
        }
        save_ticket_data(data)

        prefix = get_server_prefix(guild.id)

        embed = discord.Embed(
            title="✅ Ticket System Setup",
            color=discord.Color.green()
        )
        embed.add_field(name="Category", value=category.name, inline=False)
        embed.add_field(name="Support Role", value=support_role.mention, inline=False)
        embed.add_field(name="Log Channel", value=log_channel.mention, inline=False)
        embed.add_field(name="Panel Command", value=f"`{prefix}ticket_panel`", inline=False)
        embed.add_field(name="Buttons Command", value=f"`{prefix}ticket_buttons`", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="ticket_panel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, ctx):
        if not ctx.guild:
            return

        guild = ctx.guild
        data = load_ticket_data()
        guild_id = str(guild.id)

        if guild_id not in data:
            prefix = get_server_prefix(guild.id)
            await ctx.send(f"❌ Ticket system is not set up.\nUse `{prefix}ticket_setup @role #log-channel` first.")
            return

        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to open a ticket.",
            color=discord.Color.blurple()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text=f"{guild.name} Support")
        await ctx.send(embed=embed, view=TicketPanelView(self.bot))

    @commands.command(name="ticket_buttons")
    @commands.has_permissions(administrator=True)
    async def ticket_buttons(self, ctx):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in a ticket channel.")
            return

        ticket_id = get_ticket_custom_id_from_topic(ctx.channel.topic)

        embed = discord.Embed(
            title="🎛️ Ticket Controls",
            description=(
                f"**Ticket ID:** `{ticket_id}`\n\n"
                "Use the buttons below to export transcript or delete the ticket."
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, view=TicketControlView(self.bot))

    @commands.command(name="ticket_id")
    async def ticket_id(self, ctx):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This is not a ticket channel.")
            return

        ticket_id = get_ticket_custom_id_from_topic(ctx.channel.topic)
        await ctx.send(f"🎫 Ticket ID: `{ticket_id}`")

    @commands.command(name="transcript")
    async def transcript(self, ctx):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in a ticket channel.")
            return

        if not await can_manage_ticket(ctx.guild, ctx.author, ctx.channel):
            await ctx.send("❌ You cannot export this transcript.")
            return

        ticket_id = get_ticket_custom_id_from_topic(ctx.channel.topic) or "UNKNOWN"
        filepath = await create_transcript_file(ctx.channel, ticket_id)
        await ctx.send(f"✅ Transcript for `{ticket_id}`", file=discord.File(filepath))

    @commands.command(name="close")
    async def close_ticket(self, ctx):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This is not a ticket channel.")
            return

        if not await can_manage_ticket(ctx.guild, ctx.author, ctx.channel):
            await ctx.send("❌ You cannot close this ticket.")
            return

        await ctx.send("🗑️ Deleting ticket and saving transcript...")
        await close_ticket_and_send_transcript(ctx.guild, ctx.channel, ctx.author)

    @commands.command(name="add")
    async def add_user_to_ticket(self, ctx, member: discord.Member):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in a ticket channel.")
            return

        data = load_ticket_data()
        guild_id = str(ctx.guild.id)

        if guild_id not in data:
            await ctx.send("❌ Ticket system is not set up.")
            return

        config = data[guild_id]
        support_role_id = config.get("support_role_id")
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None

        if not (ctx.author.guild_permissions.administrator or (support_role and support_role in ctx.author.roles)):
            await ctx.send("❌ Only staff can add users to a ticket.")
            return

        ticket_id = get_ticket_custom_id_from_topic(ctx.channel.topic)

        try:
            await ctx.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
            await ctx.send(f"✅ Added {member.mention} to ticket `{ticket_id}`.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to add that user.")

    @commands.command(name="remove")
    async def remove_user_from_ticket(self, ctx, member: discord.Member):
        if not ctx.guild or not isinstance(ctx.channel, discord.TextChannel):
            return

        if not is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in a ticket channel.")
            return

        data = load_ticket_data()
        guild_id = str(ctx.guild.id)

        if guild_id not in data:
            await ctx.send("❌ Ticket system is not set up.")
            return

        config = data[guild_id]
        support_role_id = config.get("support_role_id")
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None

        if not (ctx.author.guild_permissions.administrator or (support_role and support_role in ctx.author.roles)):
            await ctx.send("❌ Only staff can remove users from a ticket.")
            return

        ticket_id = get_ticket_custom_id_from_topic(ctx.channel.topic)

        try:
            await ctx.channel.set_permissions(member, overwrite=None)
            await ctx.send(f"✅ Removed {member.mention} from ticket `{ticket_id}`.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to remove that user.")

    # -------------------------
    # Errors
    # -------------------------
    @ticket_setup.error
    async def ticket_setup_error(self, ctx, error):
        prefix = get_server_prefix(ctx.guild.id if ctx.guild else None)

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Usage: `{prefix}ticket_setup @SupportRole #log-channel`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid role or channel.\nUsage: `{prefix}ticket_setup @SupportRole #log-channel`")

    @ticket_panel.error
    async def ticket_panel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permission to use this command.")

    @ticket_buttons.error
    async def ticket_buttons_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permission to use this command.")

    @add_user_to_ticket.error
    async def add_error(self, ctx, error):
        prefix = get_server_prefix(ctx.guild.id if ctx.guild else None)

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Usage: `{prefix}add @user`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid member.")

    @remove_user_from_ticket.error
    async def remove_error(self, ctx, error):
        prefix = get_server_prefix(ctx.guild.id if ctx.guild else None)

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Usage: `{prefix}remove @user`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid member.")


# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(Ticket(bot))