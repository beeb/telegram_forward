import asyncio
import logging
import re
import sys
from collections import Counter
from typing import List, Optional, Union

from eth_typing.evm import ChecksumAddress
from eth_utils.address import to_checksum_address
from loguru import logger
from telethon import TelegramClient, events


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

tg_api_id: int = 0
tg_api_hash: str = ''
tg_channels: List[Union[int, str]] = []


async def telegram_monitor(tg_api_id: int, tg_api_hash: str, tg_channels: List[Union[int, str]], forward_to):
    global logger
    async with TelegramClient('pancakepump', tg_api_id, tg_api_hash) as client:
        username = (await client.get_me()).username
        logger.info(f'Logged into Telegram as user {username}')
        logger.info('Monitoring channel for new messages...')

        @client.on(events.NewMessage(chats=tg_channels, incoming=True))
        async def _(event):
            addr = [a.lower() for a in re.findall(r'0x[a-fA-F0-9]{40}', event.raw_text)]
            counts = Counter(addr)
            token_address: Optional[ChecksumAddress] = None
            for a, _ in counts.most_common():
                if a.startswith('0x000'):
                    continue
                token_address = to_checksum_address(a)
                break
            if token_address is not None:
                logger.success(f'Found token address in telegram message: {token_address}')

        await client.run_until_disconnected()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(telegram_monitor())


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.warning('User cancelled')
        sys.exit(0)
