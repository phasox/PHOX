import discord
from discord.ext import commands
import json
import os
import random
import time

DATA_FILE = "data/economy.json"
SHOP_FILE = "data/shop.json"
EMOJI = "<:coin:1488974719410638928>"

os.makedirs("data", exist_ok=True)

for file in [DATA_FILE, SHOP_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

def load(file):
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def get_user(data, guild, user):
    if guild not in data:
        data[guild] = {}
    if user not in data[guild]:
        data[guild][user] = {
            "balance": 0,
            "last_daily": 0,
            "inventory": {}
        }
    return data[guild][user]

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= BALANCE =================
    @commands.command(aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(member.id))

        embed = discord.Embed(
            title=f"💰 {member.name}'s Balance",
            description=f"{user['balance']} {EMOJI}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        await ctx.send(embed=embed)

    # ================= DAILY =================
    @commands.command()
    async def daily(self, ctx):
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(ctx.author.id))

        now = int(time.time())
        if now - user["last_daily"] < 86400:
            embed = discord.Embed(
                description="⏳ You already claimed daily!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        reward = random.randint(100, 300)
        user["balance"] += reward
        user["last_daily"] = now

        save(DATA_FILE, data)

        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"You got **{reward} {EMOJI}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # ================= WORK =================
    @commands.command()
    async def work(self, ctx):
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(ctx.author.id))

        reward = random.randint(20, 100)
        user["balance"] += reward

        save(DATA_FILE, data)

        embed = discord.Embed(
            title="🛠 Work",
            description=f"You earned **{reward} {EMOJI}**",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    # ================= ADMIN =================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ecogive(self, ctx, member: discord.Member, amount: int):
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(member.id))

        user["balance"] += amount
        save(DATA_FILE, data)

        embed = discord.Embed(
            description=f"✅ Gave {amount} {EMOJI} to {member.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ecoset(self, ctx, member: discord.Member, amount: int):
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(member.id))

        user["balance"] = amount
        save(DATA_FILE, data)

        embed = discord.Embed(
            description=f"✅ Set {member.mention} balance to {amount} {EMOJI}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ecorem(self, ctx, member: discord.Member, amount: int):
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(member.id))

        user["balance"] = max(0, user["balance"] - amount)
        save(DATA_FILE, data)

        embed = discord.Embed(
            description=f"✅ Removed {amount} {EMOJI} from {member.mention}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    # ================= SHOP =================
    @commands.command()
    async def shop(self, ctx):
        shop = load(SHOP_FILE)
        gid = str(ctx.guild.id)
        guild_shop = shop.get(gid, {})

        embed = discord.Embed(title="🛒 Shop", color=discord.Color.green())

        if not guild_shop:
            embed.description = "Shop is empty."
        else:
            for item, price in guild_shop.items():
                embed.add_field(
                    name=item,
                    value=f"{price} {EMOJI}",
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command()
    async def buy(self, ctx, item: str):
        data = load(DATA_FILE)
        shop = load(SHOP_FILE)

        gid = str(ctx.guild.id)
        uid = str(ctx.author.id)

        user = get_user(data, gid, uid)
        guild_shop = shop.get(gid, {})

        if item not in guild_shop:
            return await ctx.send("❌ Item not found.")

        price = guild_shop[item]

        if user["balance"] < price:
            return await ctx.send("❌ Not enough coins.")

        user["balance"] -= price
        user["inventory"][item] = user["inventory"].get(item, 0) + 1

        save(DATA_FILE, data)

        embed = discord.Embed(
            title="🛒 Purchase",
            description=f"You bought **{item}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Price", value=f"{price} {EMOJI}")

        await ctx.send(embed=embed)

    # ================= INVENTORY =================
    @commands.command(aliases=["inv"])
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(member.id))

        inv = user["inventory"]

        embed = discord.Embed(
            title=f"🎒 {member.name}'s Inventory",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        if not inv:
            embed.description = "Empty inventory."
        else:
            for item, amount in inv.items():
                embed.add_field(name=item, value=f"x{amount}", inline=False)

        await ctx.send(embed=embed)

    # ================= LEADERBOARD =================
    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):
        data = load(DATA_FILE)
        gid = str(ctx.guild.id)

        if gid not in data:
            return await ctx.send("No data.")

        users = data[gid]
        sorted_users = sorted(users.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]

        embed = discord.Embed(
            title="🏆 Leaderboard",
            color=discord.Color.gold()
        )

        desc = ""
        for i, (user_id, info) in enumerate(sorted_users, start=1):
            member = ctx.guild.get_member(int(user_id))
            name = member.name if member else "Unknown"
            desc += f"**#{i} {name}** — {info['balance']} {EMOJI}\n"

        embed.description = desc
        await ctx.send(embed=embed)

    # ================= SHOP ADMIN =================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def additem(self, ctx, name: str, price: int):
        shop = load(SHOP_FILE)
        gid = str(ctx.guild.id)

        if gid not in shop:
            shop[gid] = {}

        shop[gid][name] = price
        save(SHOP_FILE, shop)

        await ctx.send(f"✅ Added `{name}` for {price} {EMOJI}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removeitem(self, ctx, name: str):
        shop = load(SHOP_FILE)
        gid = str(ctx.guild.id)

        if gid in shop and name in shop[gid]:
            del shop[gid][name]
            save(SHOP_FILE, shop)
            await ctx.send(f"✅ Removed `{name}`")
        else:
            await ctx.send("❌ Item not found.")

# setup
async def setup(bot):
    await bot.add_cog(Economy(bot))