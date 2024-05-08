import bot
import hikari
import lightbulb
import pandas as pd
from datetime import datetime, timedelta
import asyncio

from .utils.config import settings
from .utils.log import get_logger
from .db.database import engine, Session
from .db.models import Base, User

log = get_logger(__name__)

TOKEN = settings['TOKEN']
GUILD = settings['GUILD']
ADMIN = settings['ADMIN']
FORUM_CHANNEL = settings['FORUM_CHANNEL']

app = lightbulb.BotApp(
    TOKEN,
    intents=hikari.Intents.ALL,
    default_enabled_guilds=GUILD,
    help_slash_command=True,
    banner=None
)

# Database models
# Base.metadata.drop_all(engine, tables=[Base.metadata.tables["threads"],
#                                        Base.metadata.tables["messages"]])
Base.metadata.create_all(bind=engine)

# Extensions
# app.load_extensions_from("./bot/extensions", must_exist=True)


@app.listen(hikari.StartingEvent)
async def on_starting(event: hikari.StartingEvent) -> None:
    app.d.admin = await app.rest.fetch_user(ADMIN)
    app.d.Session = Session


async def check_threads():
    CHECK_INTERVAL = 900  # 15min
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        threads = [thread
                   for thread in await app.rest.fetch_active_threads(GUILD)
                   if isinstance(thread, hikari.GuildThreadChannel)
                   and thread.parent_id == FORUM_CHANNEL
                   and thread.created_at.date() in [datetime.now().date(),
                                                    datetime.now().date() - timedelta(days=1)]]
        for thread in threads:
            if thread.approximate_member_count <= 1:
                messages: list[hikari.Message] = await thread.fetch_history()
                author = await app.rest.fetch_member(GUILD, thread.owner_id)
                attachments = [att.url for att in messages[0].attachments]

                embed = hikari.Embed(
                    title=thread.name,
                    description=messages[0].content,
                    color="#118ab2",
                    url=f"https://discord.com/channels/{thread.guild_id}/{thread.id}"
                ).set_footer(
                    text=f"Posted by {author.global_name}",
                    icon=author.avatar_url
                ).set_image(attachments[0])

                await app.rest.create_message(1237424754739253279, content=f"⚠️⏰<@&1194665960376901773> <@1214095592372969505> <@1214041211183038504> this thread remains unresolved for more than 5s", embed=embed)


@app.listen(hikari.StartedEvent)
async def on_started(event: hikari.StartedEvent) -> None:
    asyncio.create_task(check_threads())


@app.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
    exception = event.exception
    if isinstance(exception, lightbulb.CheckFailure):
        causes = exception.causes or [exception]
        error_msg = causes[0]
    else:
        raise exception
    await event.context.respond(error_msg, flags=hikari.MessageFlag.EPHEMERAL)


@app.listen(hikari.DMMessageCreateEvent)
async def on_respond(event: hikari.DMMessageCreateEvent) -> None:
    """
    Listens for DM messages and responds accordingly.

    Notes:
        - If the message author is a bot, the function returns early.
        - Extracts the URL of the referenced message's embed and retrieves the thread channel.
        - Creates a message in the thread channel with the content and attachments of the DM message.
        - Adds a reaction to the referenced message to indicate successful processing.
    """
    if event.author.is_bot:
        return

    url = event.message.referenced_message.embeds[0].url
    thread_id = url.split('/')[-1]
    thread = await app.rest.fetch_channel(thread_id)

    await app.rest.create_message(thread, content=event.content, attachments=event.message.attachments)

    await event.message.referenced_message.add_reaction("✅")


def run() -> None:
    app.run(
        activity=hikari.Activity(
            name=f"v{bot.__version__}",
            type=hikari.ActivityType.LISTENING,
            state="💡teodocs | /help")
    )