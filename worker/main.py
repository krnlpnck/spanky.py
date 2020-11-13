import asyncio

import json

from common.event import EventType
from core.manager import PluginManager
from rpc_client import RPCClient
from utils import bot_utils as butils


class PythonWorker:
    def __init__(self, evloop):
        self.loop = evloop
        # Open the bot config file
        with open("bot_config.json") as data_file:
            self.config = json.load(data_file)

        # Create the client
        self.client = RPCClient(self.config["server"], "testplm")

        self._is_ready = False

    async def connect(self):
        # Create the plugin manager
        self.plugin_manager = PluginManager(
            self.config.get("plugin_paths", ""), self)

        # Connect to the server
        await self.client.connect()

        # Inform the server about our command list
        self.cmd_list = self.client.set_command_list(
            self.plugin_manager.commands.keys()
        )

    async def run_on_ready_work(self):
        """
        Runs the work to be done when on ready is received
        """
        if self._is_ready:
            raise ValueError("Manager already marked as ready")

        self._on_ready = True

        # Get the servers
        servers = await self.client.get_servers()

        # Add current servers
        for server in servers:
            self.plugin_manager.add_new_server(server)

        await self.plugin_manager.launch_hooks_by_event(EventType.on_ready)

        asyncio.run_coroutine_threadsafe(self.timer_loop(1), self.loop)

    async def run(self):
        while True:
            evt, payload = await self.client.get_event()

            # Handle the payload type

            if evt == EventType.message:
                butils.run_in_thread(self.handle_message, args=(payload,))

            elif evt == EventType.on_ready:
                await self.run_on_ready_work()

    async def handle_message(self, message):
        if not message.content:
            return

        if message.content[0] != ".":
            return

        cmd_split = message.content[1:].split(maxsplit=1)

        command = cmd_split[0]

        # Check if it's in the command list
        if command in self.plugin_manager.commands.keys():
            hook = self.plugin_manager.commands[command]

            if len(cmd_split) > 1:
                event_text = cmd_split[1]
            else:
                event_text = ""

            # Run the command through the plugin manager
            await self.plugin_manager.launch_command(
                hook=hook, event=message, event_text=event_text)

    async def timer_loop(self, interval):
        while True:
            await asyncio.sleep(interval)

            await self.plugin_manager.launch_hooks_by_event(
                EventType.timer_event)


loop = asyncio.get_event_loop()
worker = PythonWorker(loop)

loop.run_until_complete(worker.connect())
loop.run_until_complete(worker.run())
