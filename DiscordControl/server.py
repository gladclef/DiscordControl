import concurrent.futures
import socket
import time
from datetime import datetime

import pyperclip
from pynput.keyboard import Controller, Key

UDP_IP = "127.0.0.1"
UDP_PORTs = [6332, 6333]
messages: list[tuple[int, str]] = []
keyboard = Controller()


global last_user_select_time
global last_user_select_idx
last_user_select_time = datetime.now()
last_user_select_idx = 0


def select_user(user_idx: int):
    prev_clip = pyperclip.paste()
    pyperclip.copy(str(user_idx))

    keyboard.press(Key.ctrl)
    keyboard.press(Key.shift)
    keyboard.press(Key.f22)
    keyboard.release(Key.f22)
    keyboard.release(Key.ctrl)
    keyboard.release(Key.shift)

    for i in range(100):
        if pyperclip.paste() != str(user_idx):
            break
        time.sleep(0.01)
    user_coords = pyperclip.paste()
    print(user_coords)

    pyperclip.copy(prev_clip)


def select_next_user():
    global last_user_select_time
    global last_user_select_idx

    curr = datetime.now()
    diff = (curr - last_user_select_time).total_seconds()
    last_user_select_time = curr

    if diff < 10:
        last_user_select_idx += 1

    select_user(last_user_select_idx)


def adjust_user_volume(data):
    global last_user_select_idx

    select_user(last_user_select_idx)
    
    prev_clip = pyperclip.paste()
    pyperclip.copy(str(data))

    keyboard.press(Key.ctrl_l)
    keyboard.press(Key.ctrl_r)
    keyboard.press(Key.shift_l)
    keyboard.press(Key.shift_r)
    keyboard.press('v')
    keyboard.release('v')
    keyboard.release(Key.shift_r)
    keyboard.release(Key.shift_l)
    keyboard.release(Key.ctrl_r)
    keyboard.release(Key.ctrl_l)

    time.sleep(0.05)
    pyperclip.copy(prev_clip)


def listen(ipaddr: str, port: int):
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.bind((ipaddr, port))

    while True:
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        messages.append((port, data))


# We can use a with statement to ensure threads are cleaned up promptly
with concurrent.futures.ThreadPoolExecutor(max_workers=len(UDP_PORTs)) as executor:
    # Start each listener
    futures = {executor.submit(listen, UDP_IP, port) for port in UDP_PORTs}
    
    # Wait until all futures have completed
    while True:
        if len(messages) > 0:
            messages_by_port: dict[int, str] = {}
            while len(messages) > 0:
                port, data = messages.pop()
                messages_by_port[port] = data
            
            for port in messages_by_port:
                data = messages_by_port[port]
                print("received message on port %d: %s" % (port, data))

                try:
                    if port == 6332:
                        select_next_user()
                    if port == 6333:
                        adjust_user_volume(data)
                except Exception as ex:
                    print(ex)

        time.sleep(0.05)