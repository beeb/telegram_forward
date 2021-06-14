import asyncio
import logging
import string
import sys
from typing import List, Union

import questionary
from loguru import logger
from questionary import ValidationError, Validator
from telethon import TelegramClient, events
from telethon.utils import parse_username


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logger.remove()
logger.add(
    sys.stderr,
    format="<d>{time:YYYY-MM-DD HH:mm:ss}</> <lvl>{level: ^8}</>|<lvl><n>{message}</n></lvl>",
    level='INFO',
    backtrace=False,
    diagnose=False,
    colorize=True,
)
logging.basicConfig(handlers=[InterceptHandler()], level=0)


async def telegram_monitor(
    tg_api_id: int, tg_api_hash: str, tg_channels: List[Union[int, str]], forward_to: Union[int, str]
):
    global logger
    async with TelegramClient('telegram_forward', tg_api_id, tg_api_hash) as client:
        global logger
        username = (await client.get_me()).username
        logger.info(f'Logged into Telegram as user {username}')
        logger.info('Monitoring channel(s) for new messages...')
        client.parse_mode = 'html'

        @client.on(events.NewMessage(chats=tg_channels, incoming=True))
        async def _(event):
            logger.info(f'Forwarding message: {event.raw_text[:10]}...')
            await client.send_message(forward_to, event.raw_text)

        await client.run_until_disconnected()


class IntegerValidator(Validator):
    def validate(self, document):
        if not str(document.text).isdigit():
            raise ValidationError(message='Please enter a positive integer value')


class TelegramApiHashValidator(Validator):
    def validate(self, document):
        if len(document.text) != 32 or not all(c in string.hexdigits for c in document.text):
            raise ValidationError(message='Enter a valid Telegram hash (32 hexadecimal characters)')


class TelegramUsernameOrLinkValidator(Validator):
    def validate(self, document):
        if 'joinchat' in document.text:
            raise ValidationError(message='Invite links are not supported')


def main():
    api_id = questionary.text('Please provide your Telegram App api_id:', validate=IntegerValidator).unsafe_ask()
    tg_api_hash = questionary.password(
        'Please provide your secret Telegram App api_hash:', validate=TelegramApiHashValidator
    ).unsafe_ask()
    channels = questionary.text(
        'Please provide the source channel(s) or chat(s) username(s) or ID(s)'
        + ' (you can provide multiple values separated with a comma, links accepted except for private groups):',
        validate=TelegramUsernameOrLinkValidator,
    ).unsafe_ask()
    channel_ids = [c.strip() for c in channels.split(',')]
    tg_channels = []
    for chan in channel_ids:
        try:
            cid = int(chan)
        except ValueError:
            cid, _ = parse_username(chan)
        if cid is not None:
            tg_channels.append(cid)
    if not tg_channels:
        logger.error('Could not extract a chat ID, aborting')
        return
    destination = questionary.text(
        'Please provide the destination chat ID or username (links accepted except for private groups):',
        validate=TelegramUsernameOrLinkValidator,
    ).unsafe_ask()
    try:
        forward_to = int(destination)
    except ValueError:
        forward_to, _ = parse_username(destination)
    if forward_to is None:
        logger.error('Destination chat not valid, aborting')
        return
    logger.info(f'Starting to monitor chat(s): {", ".join([str(c) for c in tg_channels])}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        telegram_monitor(tg_api_id=int(api_id), tg_api_hash=tg_api_hash, tg_channels=tg_channels, forward_to=forward_to)
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.warning('User cancelled')
        sys.exit(0)
