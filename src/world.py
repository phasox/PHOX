import discord
from discord.ext import commands
import json
import os
from config.prefix import DEFAULT_PREFIX

WORD_FILE = "data/word.json"
PREFIX_FILE = "data/prefixes.json"


def load_data():
    if os.path.exists(WORD_FILE):
        with open(WORD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(WORD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_server_prefix(guild_id):
    if os.path.exists(PREFIX_FILE):
        try:
            with open(PREFIX_FILE, "r", encoding="utf-8") as f:
                prefixes = json.load(f)
            return prefixes.get(str(guild_id), DEFAULT_PREFIX)
        except Exception:
            return DEFAULT_PREFIX
    return DEFAULT_PREFIX


class World(commands.Cog):
    """Word detection and optional role assignment with embed + non-embed commands"""

    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    def ensure_guild_data(self, guild_id: str):
        if guild_id not in self.data:
            self.data[guild_id] = {
                "role_words": [],
                "detect_words": []
            }

    # -----------------------
    # Role Word Commands (Embed)
    # -----------------------
    @commands.command(name="setroleword")
    @commands.has_permissions(manage_roles=True)
    async def set_role_word(self, ctx, word: str, role: discord.Role, required_role: discord.Role = None):
        """Assign a role when a word is typed (embed mode)"""
        guild_id = str(ctx.guild.id)
        self.ensure_guild_data(guild_id)

        self.data[guild_id]["role_words"] = [
            rw for rw in self.data[guild_id]["role_words"]
            if rw["word"] != word.lower()
        ]

        self.data[guild_id]["role_words"].append({
            "word": word.lower(),
            "role_id": role.id,
            "required_role_id": required_role.id if required_role else None,
            "mode": "embed"
        })
        save_data(self.data)

        desc = f"Saying `{word}` gives role **{role.name}**"
        if required_role:
            desc += f" only if user has **{required_role.name}**"

        embed = discord.Embed(
            title="✅ Role Word Set",
            description=desc,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="delroleword")
    @commands.has_permissions(manage_roles=True)
    async def del_role_word(self, ctx, word: str):
        """Remove a role-word configuration"""
        guild_id = str(ctx.guild.id)

        if guild_id in self.data:
            before = len(self.data[guild_id]["role_words"])
            self.data[guild_id]["role_words"] = [
                rw for rw in self.data[guild_id]["role_words"]
                if rw["word"] != word.lower()
            ]
            after = len(self.data[guild_id]["role_words"])
            save_data(self.data)

            if before != after:
                embed = discord.Embed(
                    title="✅ Role Word Removed",
                    description=f"Configuration for `{word}` removed",
                    color=discord.Color.orange()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ Not Found",
                    description=f"No role-word configuration found for `{word}`",
                    color=discord.Color.red()
                )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="⚠️ Not Found",
                description=f"No role-word configuration found for `{word}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="listrolewords")
    async def list_role_words(self, ctx):
        """List all role-word configurations"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data or not self.data[guild_id]["role_words"]:
            embed = discord.Embed(
                title="⚠️ No Role Words",
                description="No role words set on this server",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="📜 Role Words", color=discord.Color.blue())
        prefix = get_server_prefix(ctx.guild.id)

        for rw in self.data[guild_id]["role_words"]:
            role = ctx.guild.get_role(rw["role_id"])
            req_role = ctx.guild.get_role(rw["required_role_id"]) if rw["required_role_id"] else None
            role_name = role.name if role else "❌ (role missing)"
            req_text = f"(requires {req_role.name})" if req_role else ""
            mode = rw.get("mode", "embed")
            embed.add_field(
                name=f"{prefix}{rw['word']}",
                value=f"{role_name} {req_text}\nMode: **{mode}**",
                inline=False
            )

        await ctx.send(embed=embed)

    # -----------------------
    # Role Word Commands (Plain / No Embed)
    # -----------------------
    @commands.command(name="setroleword_plain")
    @commands.has_permissions(manage_roles=True)
    async def set_role_word_plain(self, ctx, word: str, role: discord.Role, required_role: discord.Role = None):
        """Assign a role when a word is typed without embeds"""
        guild_id = str(ctx.guild.id)
        self.ensure_guild_data(guild_id)

        self.data[guild_id]["role_words"] = [
            rw for rw in self.data[guild_id]["role_words"]
            if rw["word"] != word.lower()
        ]

        self.data[guild_id]["role_words"].append({
            "word": word.lower(),
            "role_id": role.id,
            "required_role_id": required_role.id if required_role else None,
            "mode": "plain"
        })
        save_data(self.data)

        msg = f"✅ Saying `{word}` gives role **{role.name}**"
        if required_role:
            msg += f" only if user has **{required_role.name}**"

        await ctx.send(msg)

    @commands.command(name="delroleword_plain")
    @commands.has_permissions(manage_roles=True)
    async def del_role_word_plain(self, ctx, word: str):
        """Remove a role-word without embeds"""
        guild_id = str(ctx.guild.id)

        if guild_id in self.data:
            before = len(self.data[guild_id]["role_words"])
            self.data[guild_id]["role_words"] = [
                rw for rw in self.data[guild_id]["role_words"]
                if rw["word"] != word.lower()
            ]
            after = len(self.data[guild_id]["role_words"])
            save_data(self.data)

            if before != after:
                await ctx.send(f"✅ Configuration for `{word}` removed")
            else:
                await ctx.send(f"⚠️ No role-word configuration found for `{word}`")
        else:
            await ctx.send(f"⚠️ No role-word configuration found for `{word}`")

    @commands.command(name="listrolewords_plain")
    async def list_role_words_plain(self, ctx):
        """Show all role-word configs without embeds"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data or not self.data[guild_id]["role_words"]:
            await ctx.send("⚠️ No role words set on this server")
            return

        prefix = get_server_prefix(ctx.guild.id)
        lines = ["📜 Role Words"]

        for rw in self.data[guild_id]["role_words"]:
            role = ctx.guild.get_role(rw["role_id"])
            req_role = ctx.guild.get_role(rw["required_role_id"]) if rw["required_role_id"] else None
            role_name = role.name if role else "❌ (role missing)"
            req_text = f" | requires {req_role.name}" if req_role else ""
            mode = rw.get("mode", "embed")
            lines.append(f"{prefix}{rw['word']} -> {role_name}{req_text} | mode: {mode}")

        await ctx.send("\n".join(lines))

    # -----------------------
    # Detect Word Commands (Embed)
    # -----------------------
    @commands.command(name="setdetectword")
    @commands.has_permissions(manage_messages=True)
    async def set_detect_word(self, ctx, word: str, *, response: str):
        """Detect a word and send a custom embed message"""
        guild_id = str(ctx.guild.id)
        self.ensure_guild_data(guild_id)

        self.data[guild_id]["detect_words"] = [
            dw for dw in self.data[guild_id]["detect_words"]
            if dw["word"] != word.lower()
        ]
        self.data[guild_id]["detect_words"].append({
            "word": word.lower(),
            "response": response,
            "mode": "embed"
        })
        save_data(self.data)

        embed = discord.Embed(
            title="✅ Detect Word Set",
            description=f"Word `{word}` will trigger a custom embed",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="deldetectword")
    @commands.has_permissions(manage_messages=True)
    async def del_detect_word(self, ctx, word: str):
        """Remove a detect-word configuration"""
        guild_id = str(ctx.guild.id)

        if guild_id in self.data:
            before = len(self.data[guild_id]["detect_words"])
            self.data[guild_id]["detect_words"] = [
                dw for dw in self.data[guild_id]["detect_words"]
                if dw["word"] != word.lower()
            ]
            after = len(self.data[guild_id]["detect_words"])
            save_data(self.data)

            if before != after:
                embed = discord.Embed(
                    title="✅ Detect Word Removed",
                    description=f"Configuration for `{word}` removed",
                    color=discord.Color.orange()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ Not Found",
                    description=f"No detect-word configuration found for `{word}`",
                    color=discord.Color.red()
                )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="⚠️ Not Found",
                description=f"No detect-word configuration found for `{word}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="listdetectwords")
    async def list_detect_words(self, ctx):
        """List all detect-word configurations"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data or not self.data[guild_id]["detect_words"]:
            embed = discord.Embed(
                title="⚠️ No Detect Words",
                description="No detect words set on this server",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="📜 Detect Words", color=discord.Color.blue())
        prefix = get_server_prefix(ctx.guild.id)

        for dw in self.data[guild_id]["detect_words"]:
            mode = dw.get("mode", "embed")
            embed.add_field(
                name=f"{prefix}{dw['word']}",
                value=f"{dw['response']}\nMode: **{mode}**",
                inline=False
            )

        await ctx.send(embed=embed)

    # -----------------------
    # Detect Word Commands (Plain / No Embed)
    # -----------------------
    @commands.command(name="setdetectword_plain")
    @commands.has_permissions(manage_messages=True)
    async def set_detect_word_plain(self, ctx, word: str, *, response: str):
        """Send a plain message whenever a word is typed"""
        guild_id = str(ctx.guild.id)
        self.ensure_guild_data(guild_id)

        self.data[guild_id]["detect_words"] = [
            dw for dw in self.data[guild_id]["detect_words"]
            if dw["word"] != word.lower()
        ]
        self.data[guild_id]["detect_words"].append({
            "word": word.lower(),
            "response": response,
            "mode": "plain"
        })
        save_data(self.data)

        await ctx.send(f"✅ Word `{word}` will trigger a plain message")

    @commands.command(name="deldetectword_plain")
    @commands.has_permissions(manage_messages=True)
    async def del_detect_word_plain(self, ctx, word: str):
        """Remove a detect-word without embeds"""
        guild_id = str(ctx.guild.id)

        if guild_id in self.data:
            before = len(self.data[guild_id]["detect_words"])
            self.data[guild_id]["detect_words"] = [
                dw for dw in self.data[guild_id]["detect_words"]
                if dw["word"] != word.lower()
            ]
            after = len(self.data[guild_id]["detect_words"])
            save_data(self.data)

            if before != after:
                await ctx.send(f"✅ Configuration for `{word}` removed")
            else:
                await ctx.send(f"⚠️ No detect-word configuration found for `{word}`")
        else:
            await ctx.send(f"⚠️ No detect-word configuration found for `{word}`")

    @commands.command(name="listdetectwords_plain")
    async def list_detect_words_plain(self, ctx):
        """Show all detect-word configs without embeds"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data or not self.data[guild_id]["detect_words"]:
            await ctx.send("⚠️ No detect words set on this server")
            return

        prefix = get_server_prefix(ctx.guild.id)
        lines = ["📜 Detect Words"]

        for dw in self.data[guild_id]["detect_words"]:
            mode = dw.get("mode", "embed")
            lines.append(f"{prefix}{dw['word']} -> {dw['response']} | mode: {mode}")

        await ctx.send("\n".join(lines))

    # -----------------------
    # Listener
    # -----------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        if guild_id not in self.data:
            return

        content = message.content.lower()

        # Role words
        for rw in self.data[guild_id]["role_words"]:
            if rw["word"] in content:
                role = message.guild.get_role(rw["role_id"])
                req_role = message.guild.get_role(rw["required_role_id"]) if rw["required_role_id"] else None
                mode = rw.get("mode", "embed")

                if req_role and req_role not in message.author.roles:
                    continue

                given_role = False
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role)
                        given_role = True
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass

                if mode == "plain":
                    if role:
                        if given_role:
                            await message.channel.send(
                                f"✅ {message.author.mention} said `{rw['word']}` and got **{role.name}**"
                            )
                        else:
                            await message.channel.send(
                                f"✅ {message.author.mention} said `{rw['word']}`"
                            )
                    else:
                        await message.channel.send(
                            f"✅ {message.author.mention} said `{rw['word']}`"
                        )
                else:
                    if role and given_role:
                        description = f"{message.author.mention} said `{rw['word']}` and received role **{role.name}**"
                    else:
                        description = f"{message.author.mention} said `{rw['word']}`"

                    embed = discord.Embed(
                        title="✅ Word Detected",
                        description=description,
                        color=discord.Color.purple()
                    )
                    await message.channel.send(embed=embed)

                break

        # Detect words
        for dw in self.data[guild_id]["detect_words"]:
            if dw["word"] in content:
                mode = dw.get("mode", "embed")

                if mode == "plain":
                    await message.channel.send(dw["response"])
                else:
                    embed = discord.Embed(
                        title="📝 Word Detected",
                        description=dw["response"],
                        color=discord.Color.gold()
                    )
                    await message.channel.send(embed=embed)

                break

    # -----------------------
    # Error Handlers
    # -----------------------
    @set_role_word.error
    @set_role_word_plain.error
    async def set_role_word_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need `Manage Roles` permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = get_server_prefix(ctx.guild.id)
            await ctx.send(
                f"Usage:\n"
                f"`{prefix}setroleword <word> <role> [required_role]`\n"
                f"`{prefix}setroleword_plain <word> <role> [required_role]`"
            )

    @set_detect_word.error
    @set_detect_word_plain.error
    async def set_detect_word_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need `Manage Messages` permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = get_server_prefix(ctx.guild.id)
            await ctx.send(
                f"Usage:\n"
                f"`{prefix}setdetectword <word> <response>`\n"
                f"`{prefix}setdetectword_plain <word> <response>`"
            )

    @del_role_word.error
    @del_role_word_plain.error
    @del_detect_word.error
    @del_detect_word_plain.error
    async def delete_word_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing word argument.")


async def setup(bot):
    await bot.add_cog(World(bot))