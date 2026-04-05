import json
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands

CONFIG_FILE = "data/config.json"


# -------------------------
# JSON Helpers
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
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data):
    ensure_data()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------
# Cog
# -------------------------
class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setlog")
    @commands.has_permissions(administrator=True)
    async def setlog(self, ctx, channel: discord.TextChannel):
        if not ctx.guild:
            return

        data = load_config()
        guild_config = data.setdefault(str(ctx.guild.id), {})
        guild_config["log_channel"] = channel.id
        save_config(data)

        embed = discord.Embed(
            title="Log Channel Updated",
            description=f"Logs will now be sent to {channel.mention}.",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)

    # -------------------------
    # Helpers
    # -------------------------
    def get_log_channel(self, guild: discord.Guild):
        data = load_config()
        guild_config = data.get(str(guild.id), {})

        channel_id = guild_config.get("log_channel") or guild_config.get("log_channel_id")
        if not channel_id:
            return None

        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return None

        return guild.get_channel(channel_id)

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = self.get_log_channel(guild)
        if channel is None:
            return

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    def base_embed(self, title: str, color: discord.Color):
        return discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

    def safe_text(self, text, limit=1000):
        if text is None:
            return "None"

        text = str(text)
        if not text.strip():
            return "None"

        if len(text) > limit:
            return text[: limit - 3] + "..."

        return text

    def fmt_roles(self, roles):
        roles = [role for role in roles if role.name != "@everyone"]
        if not roles:
            return "None"
        return ", ".join(role.mention for role in roles[:15])

    def channel_label(self, channel):
        return getattr(channel, "mention", None) or getattr(channel, "name", "Unknown")

    # -------------------------
    # MESSAGE DELETE
    # -------------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        author = message.author
        if not message.guild or getattr(author, "bot", False):
            return

        embed = self.base_embed("Message Deleted", discord.Color.red())
        embed.add_field(name="User", value=f"{author.mention} (`{author.id}`)", inline=False)
        embed.add_field(name="Channel", value=self.channel_label(message.channel), inline=False)
        embed.add_field(name="Content", value=self.safe_text(message.content), inline=False)

        if message.attachments:
            attach_list = "\n".join(attachment.url for attachment in message.attachments[:10])
            embed.add_field(name="Attachments", value=self.safe_text(attach_list), inline=False)

        await self.send_log(message.guild, embed)

    # -------------------------
    # BULK MESSAGE DELETE
    # -------------------------
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages:
            return

        first = messages[0]
        if not first.guild:
            return

        authors = []
        for message in messages[:20]:
            if message.author:
                authors.append(f"{message.author} ({message.author.id})")

        embed = self.base_embed("Bulk Messages Deleted", discord.Color.red())
        embed.add_field(name="Channel", value=self.channel_label(first.channel), inline=False)
        embed.add_field(name="Amount", value=str(len(messages)), inline=False)
        embed.add_field(name="Users", value=self.safe_text("\n".join(authors)), inline=False)

        await self.send_log(first.guild, embed)

    # -------------------------
    # MESSAGE EDIT
    # -------------------------
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        author = before.author
        if not before.guild or getattr(author, "bot", False):
            return

        if before.content == after.content:
            return

        embed = self.base_embed("Message Edited", discord.Color.orange())
        embed.add_field(name="User", value=f"{author.mention} (`{author.id}`)", inline=False)
        embed.add_field(name="Channel", value=self.channel_label(before.channel), inline=False)
        embed.add_field(name="Before", value=self.safe_text(before.content), inline=False)
        embed.add_field(name="After", value=self.safe_text(after.content), inline=False)

        try:
            embed.add_field(name="Jump", value=f"[Go to Message]({after.jump_url})", inline=False)
        except Exception:
            pass

        await self.send_log(before.guild, embed)

    # -------------------------
    # MEMBER JOIN
    # -------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = self.base_embed("Member Joined", discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="Server Members", value=str(member.guild.member_count), inline=False)

        await self.send_log(member.guild, embed)

    # -------------------------
    # MEMBER LEAVE
    # -------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = self.base_embed("Member Left", discord.Color.red())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Roles", value=self.safe_text(self.fmt_roles(member.roles)), inline=False)

        await self.send_log(member.guild, embed)

    # -------------------------
    # MEMBER UPDATE
    # -------------------------
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = self.base_embed("Nickname Changed", discord.Color.blurple())
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="Before", value=self.safe_text(before.nick), inline=True)
            embed.add_field(name="After", value=self.safe_text(after.nick), inline=True)
            await self.send_log(after.guild, embed)

        before_roles = set(before.roles)
        after_roles = set(after.roles)

        added = [role for role in after_roles - before_roles if role != after.guild.default_role]
        removed = [role for role in before_roles - after_roles if role != after.guild.default_role]

        if added or removed:
            embed = self.base_embed("Roles Updated", discord.Color.gold())
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)

            if added:
                embed.add_field(name="Added Roles", value=self.safe_text(self.fmt_roles(added)), inline=False)
            if removed:
                embed.add_field(name="Removed Roles", value=self.safe_text(self.fmt_roles(removed)), inline=False)

            await self.send_log(after.guild, embed)

        if before.timed_out_until != after.timed_out_until:
            embed = self.base_embed("Timeout Updated", discord.Color.orange())
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="Before", value=self.safe_text(before.timed_out_until), inline=False)
            embed.add_field(name="After", value=self.safe_text(after.timed_out_until), inline=False)

            await self.send_log(after.guild, embed)

        if before.display_avatar != after.display_avatar:
            embed = self.base_embed("Avatar Updated", discord.Color.blurple())
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.set_thumbnail(url=after.display_avatar.url)

            await self.send_log(after.guild, embed)

    # -------------------------
    # BAN / UNBAN
    # -------------------------
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        embed = self.base_embed("Member Banned", discord.Color.red())
        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)

        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user):
        embed = self.base_embed("Member Unbanned", discord.Color.green())
        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)

        await self.send_log(guild, embed)

    # -------------------------
    # ROLE CREATE / DELETE / UPDATE
    # -------------------------
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = self.base_embed("Role Created", discord.Color.green())
        embed.add_field(name="Role", value=f"{role.mention} (`{role.id}`)", inline=False)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)

        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = self.base_embed("Role Deleted", discord.Color.red())
        embed.add_field(name="Role", value=f"{role.name} (`{role.id}`)", inline=False)

        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` -> `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` -> `{after.color}`")
        if before.hoist != after.hoist:
            changes.append(f"**Hoist:** `{before.hoist}` -> `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` -> `{after.mentionable}`")
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` -> `{after.position}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions:** Updated")

        if not changes:
            return

        embed = self.base_embed("Role Updated", discord.Color.orange())
        embed.add_field(name="Role", value=f"{after.mention} (`{after.id}`)", inline=False)
        embed.add_field(name="Changes", value=self.safe_text("\n".join(changes)), inline=False)

        await self.send_log(after.guild, embed)

    # -------------------------
    # CHANNEL CREATE / DELETE / UPDATE
    # -------------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not hasattr(channel, "guild"):
            return

        embed = self.base_embed("Channel Created", discord.Color.green())
        embed.add_field(name="Channel", value=f"{self.channel_label(channel)} (`{channel.id}`)", inline=False)
        embed.add_field(name="Type", value=str(channel.type), inline=False)

        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not hasattr(channel, "guild"):
            return

        embed = self.base_embed("Channel Deleted", discord.Color.red())
        embed.add_field(name="Channel", value=f"{channel.name} (`{channel.id}`)", inline=False)
        embed.add_field(name="Type", value=str(channel.type), inline=False)

        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not hasattr(after, "guild"):
            return

        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` -> `{after.name}`")

        before_topic = getattr(before, "topic", None)
        after_topic = getattr(after, "topic", None)
        if before_topic != after_topic:
            changes.append(f"**Topic:** `{self.safe_text(before_topic, 200)}` -> `{self.safe_text(after_topic, 200)}`")

        if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
            changes.append(
                f"**Slowmode:** `{getattr(before, 'slowmode_delay', 0)}` -> `{getattr(after, 'slowmode_delay', 0)}`"
            )

        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            changes.append(f"**NSFW:** `{getattr(before, 'nsfw', None)}` -> `{getattr(after, 'nsfw', None)}`")

        if getattr(before, "category_id", None) != getattr(after, "category_id", None):
            changes.append("**Category:** Updated")

        if not changes:
            return

        embed = self.base_embed("Channel Updated", discord.Color.orange())
        embed.add_field(name="Channel", value=f"{self.channel_label(after)} (`{after.id}`)", inline=False)
        embed.add_field(name="Changes", value=self.safe_text("\n".join(changes)), inline=False)

        await self.send_log(after.guild, embed)

    # -------------------------
    # THREAD CREATE / DELETE / UPDATE
    # -------------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        embed = self.base_embed("Thread Created", discord.Color.green())
        embed.add_field(name="Thread", value=f"{thread.mention} (`{thread.id}`)", inline=False)
        embed.add_field(name="Parent", value=self.channel_label(thread.parent) if thread.parent else "Unknown", inline=False)

        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = self.base_embed("Thread Deleted", discord.Color.red())
        embed.add_field(name="Thread", value=f"{thread.name} (`{thread.id}`)", inline=False)

        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` -> `{after.name}`")
        if before.archived != after.archived:
            changes.append(f"**Archived:** `{before.archived}` -> `{after.archived}`")
        if before.locked != after.locked:
            changes.append(f"**Locked:** `{before.locked}` -> `{after.locked}`")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"**Slowmode:** `{before.slowmode_delay}` -> `{after.slowmode_delay}`")

        if not changes:
            return

        embed = self.base_embed("Thread Updated", discord.Color.orange())
        embed.add_field(name="Thread", value=f"{after.name} (`{after.id}`)", inline=False)
        embed.add_field(name="Changes", value=self.safe_text("\n".join(changes)), inline=False)

        await self.send_log(after.guild, embed)

    # -------------------------
    # VOICE LOGS
    # -------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None:
            embed = self.base_embed("Voice Join", discord.Color.green())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Channel", value=self.channel_label(after.channel), inline=False)
            await self.send_log(member.guild, embed)
            return

        if before.channel is not None and after.channel is None:
            embed = self.base_embed("Voice Leave", discord.Color.red())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Channel", value=self.channel_label(before.channel), inline=False)
            await self.send_log(member.guild, embed)
            return

        if before.channel != after.channel:
            embed = self.base_embed("Voice Move", discord.Color.orange())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="From", value=self.channel_label(before.channel) if before.channel else "None", inline=True)
            embed.add_field(name="To", value=self.channel_label(after.channel) if after.channel else "None", inline=True)
            await self.send_log(member.guild, embed)
            return

        if before.self_mute != after.self_mute:
            embed = self.base_embed("Self Mute Updated", discord.Color.blurple())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Muted", value=str(after.self_mute), inline=False)
            await self.send_log(member.guild, embed)

        if before.self_deaf != after.self_deaf:
            embed = self.base_embed("Self Deaf Updated", discord.Color.blurple())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Deafened", value=str(after.self_deaf), inline=False)
            await self.send_log(member.guild, embed)

        if before.stream != after.stream:
            embed = self.base_embed("Stream Status Updated", discord.Color.purple())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Streaming", value=str(after.stream), inline=False)
            await self.send_log(member.guild, embed)

        if before.self_video != after.self_video:
            embed = self.base_embed("Camera Status Updated", discord.Color.blurple())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Camera", value=str(after.self_video), inline=False)
            await self.send_log(member.guild, embed)

    # -------------------------
    # INVITE CREATE / DELETE
    # -------------------------
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if not invite.guild:
            return

        embed = self.base_embed("Invite Created", discord.Color.green())
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=self.channel_label(invite.channel) if invite.channel else "Unknown", inline=True)
        embed.add_field(name="Creator", value=invite.inviter.mention if invite.inviter else "Unknown", inline=False)
        embed.add_field(name="Uses", value=str(invite.uses or 0), inline=True)
        embed.add_field(name="Max Uses", value=str(invite.max_uses or 0), inline=True)

        await self.send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if not invite.guild:
            return

        embed = self.base_embed("Invite Deleted", discord.Color.red())
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=self.channel_label(invite.channel) if invite.channel else "Unknown", inline=True)

        await self.send_log(invite.guild, embed)

    # -------------------------
    # EMOJI / STICKER UPDATES
    # -------------------------
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        before_ids = {emoji.id for emoji in before}
        after_ids = {emoji.id for emoji in after}

        added = [emoji for emoji in after if emoji.id not in before_ids]
        removed = [emoji for emoji in before if emoji.id not in after_ids]

        if added:
            embed = self.base_embed("Emoji Added", discord.Color.green())
            embed.add_field(name="Emoji", value=self.safe_text(", ".join(str(emoji) for emoji in added)), inline=False)
            await self.send_log(guild, embed)

        if removed:
            embed = self.base_embed("Emoji Removed", discord.Color.red())
            embed.add_field(
                name="Emoji",
                value=self.safe_text(", ".join(f"{emoji.name} (`{emoji.id}`)" for emoji in removed)),
                inline=False,
            )
            await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild, before, after):
        before_ids = {sticker.id for sticker in before}
        after_ids = {sticker.id for sticker in after}

        added = [sticker for sticker in after if sticker.id not in before_ids]
        removed = [sticker for sticker in before if sticker.id not in after_ids]

        if added:
            embed = self.base_embed("Sticker Added", discord.Color.green())
            embed.add_field(
                name="Sticker",
                value=self.safe_text(", ".join(f"{sticker.name} (`{sticker.id}`)" for sticker in added)),
                inline=False,
            )
            await self.send_log(guild, embed)

        if removed:
            embed = self.base_embed("Sticker Removed", discord.Color.red())
            embed.add_field(
                name="Sticker",
                value=self.safe_text(", ".join(f"{sticker.name} (`{sticker.id}`)" for sticker in removed)),
                inline=False,
            )
            await self.send_log(guild, embed)

    # -------------------------
    # SERVER UPDATE
    # -------------------------
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` -> `{after.name}`")
        if before.description != after.description:
            changes.append(f"**Description:** `{self.safe_text(before.description, 200)}` -> `{self.safe_text(after.description, 200)}`")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification:** `{before.verification_level}` -> `{after.verification_level}`")
        if before.afk_timeout != after.afk_timeout:
            changes.append(f"**AFK Timeout:** `{before.afk_timeout}` -> `{after.afk_timeout}`")
        if before.system_channel != after.system_channel:
            changes.append("**System Channel:** Updated")

        if not changes:
            return

        embed = self.base_embed("Server Updated", discord.Color.orange())
        embed.add_field(name="Server", value=f"{after.name} (`{after.id}`)", inline=False)
        embed.add_field(name="Changes", value=self.safe_text("\n".join(changes)), inline=False)

        await self.send_log(after, embed)


# -------------------------
# Setup
# -------------------------
async def setup(bot):
    await bot.add_cog(Logs(bot))
