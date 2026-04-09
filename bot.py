import os
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://scoutscode.net"
EMBED_DESCRIPTION_LIMIT = 4096


def format_rule(data: dict, lines: list | None = None) -> str:
    """Flatten a rule and its children into a list of bold-section lines."""
    if lines is None:
        lines = []
    lines.append(f"**{data['section']}** {data['text']}")
    for child in data.get("children", []):
        format_rule(child, lines)
    return "\n".join(lines)


async def fetch_rule(rule_type: str, section: str) -> dict | None:
    """
    Fetch a rule from the scoutscode API.
    Returns the JSON dict on success, None if not found, raises on other errors.
    """
    url = f"{BASE_URL}/api/rules/{rule_type}/{section}/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return await resp.json()
            if resp.status == 404:
                return None
            resp.raise_for_status()


async def rule_command(interaction: discord.Interaction, rule_type: str, section: str):
    """Shared handler for /cr and /tr."""
    await interaction.response.defer()

    try:
        data = await fetch_rule(rule_type, section)
    except Exception as e:
        await interaction.followup.send(f"Error contacting the rules API: {e}")
        return

    if data is None:
        label = rule_type.upper()
        await interaction.followup.send(f"**{label} {section}** was not found.")
        return

    label = rule_type.upper()
    page_type = "crsections" if rule_type == "cr" else "trsections"
    page_url = f"{BASE_URL}/{page_type}/{data['section']}/"
    color = discord.Color.blue() if rule_type == "cr" else discord.Color.gold()

    description = format_rule(data)
    if len(description) > EMBED_DESCRIPTION_LIMIT:
        suffix = f"\n\n*[Rule truncated — view full text on scoutscode.net]({page_url})*"
        cutoff = description[: EMBED_DESCRIPTION_LIMIT - len(suffix)]
        description = cutoff[: cutoff.rfind("\n")] + suffix

    embed = discord.Embed(
        title=f"{label} {data['section']}",
        description=description,
        url=page_url,
        color=color,
    )
    await interaction.followup.send(embed=embed)


intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=1491598238942494920,
)


@bot.tree.command(name="cr", description="Look up a Riftbound Comprehensive Rule")
@app_commands.describe(section="Rule section, e.g. 703 or 703.4 or 703.4.a")
async def cr_command(interaction: discord.Interaction, section: str):
    await rule_command(interaction, "cr", section)


@bot.tree.command(name="tr", description="Look up a Riftbound Tournament Rule")
@app_commands.describe(section="Rule section, e.g. 301 or 301.1")
async def tr_command(interaction: discord.Interaction, section: str):
    await rule_command(interaction, "tr", section)


@bot.event
async def on_ready():
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Slash commands synced to guild {guild_id} (instant).")
    else:
        await bot.tree.sync()
        print("Slash commands synced globally (may take up to 1 hour to appear).")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    bot.run(token)
