import discord
from discord.ext import commands
import random
import string
import io
import json
import os

from PIL import Image, ImageDraw, ImageFont

CONFIG_FILE = "data/verify_config.json"
active_captchas = {}


# ---------------- CONFIG ---------------- #

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# ---------------- CAPTCHA ---------------- #

def generate_captcha_text(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_captcha_image(text):
    width, height = 340, 140
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
    except:
        font = ImageFont.load_default()

    # Background grid
    for x in range(0, width, 25):
        draw.line((x, 0, x, height), fill=(225, 225, 225))
    for y in range(0, height, 25):
        draw.line((0, y, width, y), fill=(225, 225, 225))

    spacing = width // (len(text) + 1)

    for i, char in enumerate(text):
        color = (
            random.randint(20, 140),
            random.randint(20, 140),
            random.randint(20, 140)
        )

        char_img = Image.new("RGBA", (70, 90), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((12, 10), char, font=font, fill=color)

        char_img = char_img.rotate(random.randint(-28, 28), expand=1)

        x = spacing * (i + 1) - 25
        y = random.randint(18, 38)

        image.paste(char_img, (x, y), char_img)

    # Noise lines
    for _ in range(4):
        draw.line(
            (
                random.randint(0, width),
                random.randint(0, height),
                random.randint(0, width),
                random.randint(0, height),
            ),
            fill=(120, 120, 120),
            width=1,
        )

    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


# ---------------- VIEWS ---------------- #

class VerifyView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Start Captcha",
        style=discord.ButtonStyle.green,
        emoji="<:verify:1488977541128785993>",
        custom_id="verify_start_captcha"
    )
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ This can only be used in a server.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

        guild_id = str(guild.id)

        if guild_id not in config:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Verification Not Configured",
                    description="Ask an admin to run `!verify_setup @role #log-channel` first.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

        captcha = generate_captcha_text()
        active_captchas[interaction.user.id] = {
            "captcha": captcha,
            "guild_id": guild.id,
            "channel_id": interaction.channel.id if interaction.channel else None
        }

        image = generate_captcha_image(captcha)
        file = discord.File(image, filename="captcha.png")

        embed = discord.Embed(
            title="<:verify:1488977541128785993> Captcha Verification",
            description=(
                f"Type the captcha **in {interaction.channel.mention}**.\n\n"
                f"Your message will be deleted automatically."
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://captcha.png")
        embed.set_footer(text=f"{guild.name} • Verification System")

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


# ---------------- COG ---------------- #

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerifyView(bot))

    @commands.command(name="verify_setup")
    @commands.has_permissions(administrator=True)
    async def verify_setup(self, ctx, role: discord.Role, log_channel: discord.TextChannel):
        config = load_config()
        config[str(ctx.guild.id)] = {
            "role": role.id,
            "log": log_channel.id
        }
        save_config(config)

        embed = discord.Embed(
            title="✅ Verification Setup Complete",
            description=(
                f"**Role:** {role.mention}\n"
                f"**Log Channel:** {log_channel.mention}"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"{ctx.guild.name} • Setup Saved")

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.send(embed=embed)

    @commands.command(name="verify_panel")
    @commands.has_permissions(administrator=True)
    async def verify_panel(self, ctx):
        config = load_config()

        if str(ctx.guild.id) not in config:
            embed = discord.Embed(
                title="❌ Verification Not Setup",
                description="Run `!verify_setup @role #log-channel` first.",
                color=discord.Color.red()
            )
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            embed.set_footer(text=ctx.guild.name)
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title=f"<:verify:1488977541128785993> Welcome to {ctx.guild.name}",
            description=(
                "**Verification Required**\n\n"
                "Click the button below to start the captcha.\n"
                "After that, type the code in chat to get access."
            ),
            color=discord.Color.green()
        )

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.add_field(
            name="How it works",
            value=(
                "1. Click **Start Captcha**\n"
                "2. View the generated image\n"
                "3. Type the code in chat\n"
                "4. Get verified automatically"
            ),
            inline=False
        )

        embed.add_field(
            name="Security",
            value="Wrong answers are deleted automatically.",
            inline=False
        )

        embed.set_footer(text=f"{ctx.guild.name} • Secure Verification")

        await ctx.send(embed=embed, view=VerifyView(self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_data = active_captchas.get(message.author.id)
        if not user_data:
            return

        if user_data["guild_id"] != message.guild.id:
            return

        captcha = user_data["captcha"]
        config = load_config()
        guild_id = str(message.guild.id)

        if guild_id not in config:
            active_captchas.pop(message.author.id, None)
            return

        try:
            await message.delete()
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        role = message.guild.get_role(config[guild_id]["role"])
        log_channel = message.guild.get_channel(config[guild_id]["log"])

        if message.content.upper() == captcha:
            if role:
                try:
                    await message.author.add_roles(role, reason="Passed verification captcha")
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass

            active_captchas.pop(message.author.id, None)

            success_embed = discord.Embed(
                title="<:verify:1488977541128785993> User Verified",
                description=f"{message.author.mention} passed verification and received the role.",
                color=discord.Color.green()
            )
            success_embed.add_field(name="User", value=f"{message.author} (`{message.author.id}`)", inline=False)
            success_embed.set_footer(text=message.guild.name)

            if message.guild.icon:
                success_embed.set_thumbnail(url=message.guild.icon.url)

            if log_channel:
                try:
                    await log_channel.send(embed=success_embed)
                except discord.HTTPException:
                    pass

            try:
                user_embed = discord.Embed(
                    title="<:verify:1488977541128785993> Verification Successful",
                    description=f"You have been verified in **{message.guild.name}**.",
                    color=discord.Color.green()
                )
                if message.guild.icon:
                    user_embed.set_thumbnail(url=message.guild.icon.url)
                await message.author.send(embed=user_embed)
            except discord.HTTPException:
                pass

        else:
            fail_embed = discord.Embed(
                title="⚠️ Failed Verification Attempt",
                description=f"{message.author.mention} entered the wrong captcha.",
                color=discord.Color.orange()
            )
            fail_embed.add_field(name="User", value=f"{message.author} (`{message.author.id}`)", inline=False)
            fail_embed.set_footer(text=message.guild.name)

            if message.guild.icon:
                fail_embed.set_thumbnail(url=message.guild.icon.url)

            if log_channel:
                try:
                    await log_channel.send(embed=fail_embed)
                except discord.HTTPException:
                    pass

            try:
                user_fail_embed = discord.Embed(
                    title="❌ Wrong Captcha",
                    description="Your answer was invalid. Press the button again to generate a new captcha.",
                    color=discord.Color.red()
                )
                if message.guild.icon:
                    user_fail_embed.set_thumbnail(url=message.guild.icon.url)
                await message.author.send(embed=user_fail_embed)
            except discord.HTTPException:
                pass

            active_captchas.pop(message.author.id, None)


async def setup(bot):
    await bot.add_cog(Verify(bot))