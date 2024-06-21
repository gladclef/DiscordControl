import concurrent.futures
import socket
import time
from datetime import datetime, timedelta

import discord_interaction.dapi as dapi
from pynput.keyboard import Controller, Key

UDP_IP = "127.0.0.1"
UDP_PORTs = [6331, 6332, 6333]

global action_queue
messages: list[tuple[int, str]] = []
keyboard = Controller()
action_queue: list["Action"] = []


global last_user_select_time
global last_user_volume_adj_time
global last_user_select_idx
last_user_select_time = datetime.now() - timedelta(hours=1)
last_user_volume_adj_time = datetime.now() - timedelta(hours=1)
last_user_select_idx = 0


class Action():
    def __init__(self, action_type: str, data: float = 0):
        self.action_type = action_type
        self.data = data


def select_user(user_idx: int):
    dapi.mouse_over_user(user_idx)


def select_next_user():
    global last_user_select_time
    global last_user_volume_adj_time
    global last_user_select_idx

    curr = datetime.now()
    diff = (curr - last_user_select_time).total_seconds()
    last_user_select_time = curr
    last_user_volume_adj_time = curr - timedelta(hours=1)

    if diff < 3:
        last_user_select_idx += 1

    select_user(last_user_select_idx)


def adjust_user_volume(data: float):
    global last_user_volume_adj_time
    global last_user_select_idx

    curr = datetime.now()
    diff = (curr - last_user_volume_adj_time).total_seconds()
    last_user_volume_adj_time = curr
    dont_open_context_menu = diff < 3

    dapi.set_user_volume(last_user_select_idx, int(data * 100), dont_open_context_menu)


def evaluate_actions():
    global action_queue

    while True:
        if len(action_queue) > 0:
            last_action = action_queue[-1]

            if last_action.action_type == "mute":
                action_queue = list(filter(lambda a: a.action_type != last_action.action_type, action_queue))
                try:
                    if last_action.data < 0.5:
                        dapi.mute()
                    else:
                        dapi.unmute()
                except Exception as ex:
                    print(last_action.action_type + ": " + repr(ex))
                    pass

            elif last_action.action_type == "next_user":
                action_queue = list(filter(lambda a: a.action_type != last_action.action_type, action_queue))
                try:
                    select_next_user()
                except Exception as ex:
                    print(last_action.action_type + ": " + repr(ex))
                    pass

            elif last_action.action_type == "set_volume":
                action_queue = list(filter(lambda a: a.action_type != last_action.action_type, action_queue))
                try:
                    adjust_user_volume(last_action.data)
                except Exception as ex:
                    print(last_action.action_type + ": " + repr(ex))
                    pass

        time.sleep(0.01)


def listen(ipaddr: str, port: int):
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.bind((ipaddr, port))

    while True:
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        messages.append((port, data))


if __name__ == "__main__":
    # We can use a with statement to ensure threads are cleaned up promptly
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(UDP_PORTs)+1) as executor:
        # Start each listener
        futures = [executor.submit(listen, UDP_IP, port) for port in UDP_PORTs]
        futures.append(executor.submit(evaluate_actions))
        
        # Wait until all futures have completed
        while True:
            if len(messages) > 0:
                messages_by_port: dict[int, str] = {}
                while len(messages) > 0:
                    port, data = messages.pop()
                    messages_by_port[port] = data
                
                for port in messages_by_port:
                    data = messages_by_port[port]
                    data = float(data.decode("utf-8"))
                    print("received message on port %d: %f" % (port, data))

                    try:
                        if port == 6331:
                            action_queue.append(Action("mute", data))
                        if port == 6332:
                            action_queue.append(Action("next_user"))
                        if port == 6333:
                            action_queue.append(Action("set_volume", data))
                    except Exception as ex:
                        print(ex)

            time.sleep(0.05)