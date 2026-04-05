import discord
from discord.ext import commands
import random
from .economy import DATA_FILE, load, save, get_user, EMOJI

class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= SLOTS =================
    @commands.command()
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(ctx.author.id))

        if user["balance"] < amount:
            return await ctx.send("❌ Not enough coins.")

        user["balance"] -= amount

        emojis = ["🍒", "🍋", "🍊", "🍉", "⭐", "7️⃣", "<:PhaseCoin:1483508920738643988>"]
        result = [random.choice(emojis) for _ in range(3)]

        embed = discord.Embed(
            title="🎰 Slots Machine",
            color=discord.Color.purple()
        )
        embed.add_field(name="Result", value=" | ".join(result), inline=False)

        # Check winnings
        if result[0] == result[1] == result[2]:
            winnings = amount * 5
            user["balance"] += winnings
            embed.add_field(name="🎉 Jackpot!", value=f"You won {winnings} {EMOJI}")
        elif len(set(result)) == 2:  # two match
            winnings = amount * 2
            user["balance"] += winnings
            embed.add_field(name="🎉 Win!", value=f"You won {winnings} {EMOJI}")
        else:
            embed.add_field(name="💔 Lose", value=f"You lost {amount} {EMOJI}")

        save(DATA_FILE, data)
        await ctx.send(embed=embed)

    # ================= COINFLIP =================
    @commands.command()
    async def coinflip(self, ctx, amount: int, choice: str):
        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        choice = choice.lower()
        if choice not in ["heads", "tails"]:
            return await ctx.send("❌ Choose heads or tails.")

        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(ctx.author.id))

        if user["balance"] < amount:
            return await ctx.send("❌ Not enough coins.")

        user["balance"] -= amount
        flip = random.choice(["heads", "tails"])

        embed = discord.Embed(title="🪙 Coinflip", color=discord.Color.gold())
        embed.add_field(name="Result", value=flip.capitalize(), inline=False)

        if flip == choice:
            winnings = amount * 2
            user["balance"] += winnings
            embed.add_field(name="🎉 You Won!", value=f"You won {winnings} {EMOJI}")
        else:
            embed.add_field(name="💔 You Lost", value=f"You lost {amount} {EMOJI}")

        save(DATA_FILE, data)
        await ctx.send(embed=embed)

    # ================= BLACKJACK =================
    @commands.command()
    async def blackjack(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ Invalid amount.")

        data = load(DATA_FILE)
        user = get_user(data, str(ctx.guild.id), str(ctx.author.id))

        if user["balance"] < amount:
            return await ctx.send("❌ Not enough coins.")

        user["balance"] -= amount

        def deal_card():
            cards = [2,3,4,5,6,7,8,9,10,10,10,10,11]
            return random.choice(cards)

        player = [deal_card(), deal_card()]
        dealer = [deal_card(), deal_card()]

        player_total = sum(player)
        dealer_total = sum(dealer)

        # Dealer draws until 17+
        while dealer_total < 17:
            dealer.append(deal_card())
            dealer_total = sum(dealer)

        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_blue())
        embed.add_field(name="Your hand", value=f"{player} = {player_total}", inline=False)
        embed.add_field(name="Dealer hand", value=f"{dealer} = {dealer_total}", inline=False)

        if player_total > 21:
            result = f"💔 Bust! You lost {amount} {EMOJI}"
        elif dealer_total > 21 or player_total > dealer_total:
            winnings = amount * 2
            user["balance"] += winnings
            result = f"🎉 You win! You earned {winnings} {EMOJI}"
        elif player_total == dealer_total:
            user["balance"] += amount
            result = f"🤝 Tie! Your bet is returned {amount} {EMOJI}"
        else:
            result = f"💔 You lost {amount} {EMOJI}"

        embed.add_field(name="Result", value=result, inline=False)
        save(DATA_FILE, data)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Casino(bot))