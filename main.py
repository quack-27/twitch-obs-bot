import asyncio
import os
import json
import psutil
from datetime import datetime, timedelta
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent, AuthType
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatCommand
from twitchAPI.helper import first
import obsws_python as obs2
#import supermegaoverwatchskills

# commands:
# !ban <user> <reason> | bans someone. if the reason is bot it will put their name in the detected_bots file so u can report then to twitch later
# !tmo <user> <minutes> <reason> | timeout someone
# !uban <user> | unbands someone

# ALL MUTE COMMANDS BELOW  TOGGLE THE MICS, SO IF U ARE MUTED BUT UR FRIEDNDS ARE UN MUTES, IT WILL MUTE U AND UNMUTE UR FRIENDS
# !mme | mutes ur mic
# !mf  | mutes friends mic
# !mm | mutes your and your firends mics
# !mg | mutes the game audio
# !ma | mutes ur mic, ur firiends mics, mutes the game audio
# ALL MISC COMMANDS BELOW
# !death | adds a death to an obs death counter
# !timer | starts a obs timer



OBS_PASSWORD = ''  # gets from the obs websocket setup
APP_ID = '' # gets from your twtich bot from the dev page
APP_SECRET = ''# gets from your twtich bot from the dev page
TARGET_CHANNEL = ''# your chanel name


# These are the names of your input mics and game audio no thte uuids. not suitable for a big obs with several things that could have tha same names if needed look up how to cponvert to uuids
# the ones here are just mine for examples
MY_MIC = 'Mymic' 
FR_MIC = 'Chatfriends'
GAME_AUDIO = 'GameAudio'
DEATH_TEXT_SOURCE = "Death Counter"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'tokens.json')
BOT_FOLDER = os.path.join(SCRIPT_DIR, "detected_bots.txt")
DEATHS_FILE = os.path.join(SCRIPT_DIR, "deaths.txt")
TIMER_FILE = os.path.join(SCRIPT_DIR, "timer.txt")


GREEN, RED, RESET = '\033[92m', '\033[91m', '\033[0m'

USER_SCOPE = [
    AuthScope.CHAT_READ, 
    AuthScope.CHAT_EDIT, 
    AuthScope.MODERATOR_MANAGE_BANNED_USERS,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES
]


cl = None
twitch = None
chat = None
broadcaster_id = None
bot_id = None
deaths = 0
timer_running = False
current_seconds = 0


def load_deaths():
    global deaths
    if os.path.exists(DEATHS_FILE):
        with open(DEATHS_FILE, "r") as f:
            try:
                deaths = int(f.read().strip())
            except: deaths = 0
    else:
        deaths = 0
    return deaths

def save_deaths():
    with open(DEATHS_FILE, "w") as f:
        f.write(str(deaths))

def log_bot(username):
    with open(BOT_FOLDER, "a") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {username}\n")

def is_obs_running():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'obs64.exe': return True
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return False


def update_obs_death_text():
    if cl:
        try:
            cl.set_input_settings(DEATH_TEXT_SOURCE, {'text': f"Deaths: {deaths}"}, overlay=True)
        except Exception as e:
            print(f"{RED}Failed to update OBS text: {e}{RESET}")


async def ban_command(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    
    if len(cmd.parameter) == 0: return
    parts = cmd.parameter.split(' ')
    target_username = parts[0]
    reason = ' '.join(parts[1:]) if len(parts) > 1 else 'no reason stated'
    
    if "bot" in reason.lower():
        log_bot(target_username)
        print(f"{RED}Logged bot: {target_username}{RESET}")

    target_info = await first(twitch.get_users(logins=[target_username]))
    if target_info:
        await twitch.ban_user(broadcaster_id, bot_id, target_info.id, reason)

async def timeout_command(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    
    parts = cmd.parameter.split(' ')
    if len(parts) < 2: return
    try:
        target_username = parts[0]
        duration = int(parts[1]) * 60
        reason = ' '.join(parts[2:]) if len(parts) > 2 else 'no reason stated'
        target_info = await first(twitch.get_users(logins=[target_username]))
        if target_info:
            await twitch.ban_user(broadcaster_id, bot_id, target_info.id, reason, duration)
            print(f"{RED}Timeout sent for {target_username} ({duration} seconds){RESET}")
    except: pass

async def unban_command(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    
    if len(cmd.parameter) == 0: return
    target_username = cmd.parameter.split(' ')[0]
    target_info = await first(twitch.get_users(logins=[target_username]))
    if target_info:
        await twitch.unban_user(broadcaster_id, bot_id, target_info.id)


async def on_ready(ready_event: EventData):
    await ready_event.chat.join_room(TARGET_CHANNEL)
    print(f"{RED}bot joined {TARGET_CHANNEL}{RESET}")

async def on_message(msg: ChatMessage):
    print(f"{GREEN}{msg.user.name}: {msg.text}{RESET}")

async def eldenring_death(cmd: ChatCommand):
    global deaths
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    
    deaths += 1
    save_deaths()
    update_obs_death_text()
    print(f"{GREEN}Death recorded! Total: {deaths}{RESET}")


async def mute_mine(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    if cl: cl.toggle_input_mute(MY_MIC)

async def mute_friends(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    if cl: cl.toggle_input_mute(FR_MIC)

async def mute_mics(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    if cl:
        cl.toggle_input_mute(MY_MIC)
        cl.toggle_input_mute(FR_MIC)

async def mute_game(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    if cl: cl.toggle_input_mute(GAME_AUDIO)

async def mute_all(cmd: ChatCommand):
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass
    if cl:
        cl.toggle_input_mute(MY_MIC)
        cl.toggle_input_mute(FR_MIC)
        cl.toggle_input_mute(GAME_AUDIO)

async def toggle_timer(cmd: ChatCommand):
    global timer_running
    if not cmd.user.mod and cmd.user.name != TARGET_CHANNEL: return
    try: await twitch.delete_chat_message(broadcaster_id, bot_id, cmd.id)
    except: pass

    timer_running = not timer_running 
    state = "STARTED" if timer_running else "PAUSED"
    print(f"{GREEN}Timer is now {state}{RESET}")

async def timer_background_task():
    global current_seconds, timer_running
  
    if os.path.exists(TIMER_FILE):
        try:
            with open(TIMER_FILE, "r") as f:
                current_seconds = int(f.read().strip())
        except: current_seconds = 0

    while True:
        if timer_running:
            current_seconds += 1
 
            with open(TIMER_FILE, "w") as f:
                f.write(str(current_seconds))
            

            if cl:
                readable_time = str(timedelta(seconds=current_seconds)).zfill(8)
                cl.set_input_settings("Timer", {'text': readable_time}, overlay=True)
        
        await asyncio.sleep(1) 


async def start_twitch_bot():
    global twitch, broadcaster_id, bot_id, chat
    if chat and chat.is_connected(): return

    asyncio.create_task(timer_background_task())
    
    print(f"{RED}logging into twitch...{RESET}")
    twitch = await Twitch(APP_ID, APP_SECRET)

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            data = json.load(f)
            try:
                await twitch.set_user_authentication(data['token'], USER_SCOPE, data['refresh'])
            except:
                os.remove(TOKEN_FILE)

    if not twitch.has_required_auth(AuthType.USER, USER_SCOPE):
        auth = UserAuthenticator(twitch, USER_SCOPE)
        token, refresh_token = await auth.authenticate()
        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
        with open(TOKEN_FILE, 'w') as f:
            json.dump({'token': token, 'refresh': refresh_token}, f)

    me = await first(twitch.get_users())
    bot_id = me.id
    user = await first(twitch.get_users(logins=[TARGET_CHANNEL]))
    broadcaster_id = user.id

    chat = await Chat(twitch)
    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    
    chat.register_command('ban', ban_command)
    chat.register_command('tmo', timeout_command)
    chat.register_command('uban', unban_command)
    
    chat.register_command('death', eldenring_death)
    chat.register_command('mme', mute_mine)
    chat.register_command('mf', mute_friends)
    chat.register_command('mm', mute_mics)
    chat.register_command('mg', mute_game)
    chat.register_command('ma', mute_all)
    chat.register_command('timer', toggle_timer)
    
    chat.start()
    print(f"{RED}Login process complete! Bot is active.{RESET}")


async def run_main():
    global cl
    load_deaths()
    
    while True:
        if not is_obs_running():
            print(f"{RED}searching for obs...{RESET}")
            await asyncio.sleep(5)
            continue
        
        try:
            print(f"{RED}obs found. connecting to websocket...{RESET}")
            cl = obs2.ReqClient(host='localhost', port=4455, password=OBS_PASSWORD)

            update_obs_death_text()
            await start_twitch_bot()

            while is_obs_running():
                await asyncio.sleep(5)
                
            print(f"{RED}OBS was closed, waiting to reconnect{RESET}")
        except Exception as e:
            print(f"{RED}websocket connection error: {e}{RESET}")
            await asyncio.sleep(10)
        finally:
            cl = None

if __name__ == "__main__":
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print(f"{RED}manual stop{RESET}")