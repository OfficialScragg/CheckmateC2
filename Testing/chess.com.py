import os
import requests
import math
import base64
import time
import random
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

WAIT_TIME = 5
JITTER = 3

CHESS_COM_COOKIE = os.getenv("AGENT_CHESS_COM_COOKIE", "")
CHESS_UPLOAD_TOKEN = os.getenv("AGENT_UPLOAD_TOKEN", "")
CHESS_CLEAR_TOKEN = os.getenv("AGENT_CLEAR_TOKEN", "")
MY_COLLECTION = os.getenv("AGENT_MY_COLLECTION_ID", "3186ea38-1cc5-11f1-a1c5-ad1d0ff2ef4e")

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

    pgn_template = ("[Event \"?\"]\n[Site \"?\"]\n[Date \"????.??.??\"]\n[Round \"?\"]\n[White \"?\"]\n[Black \"?\"]\n[Result \"*\"]\n[SetUp \"1\"]\n[FEN \"{fen}\"]\n\n*")

    for fen in games:
        try:
            data = {
                "_token": CHESS_UPLOAD_TOKEN,
                "pgn": pgn_template.format(fen=fen),
            }
            response = requests.post(
                f"https://www.chess.com/callback/library/collections/{MY_COLLECTION}/actions/add-from-pgn",
                headers=headers,
                json=data,
            )
            response.raise_for_status()
            time.sleep(WAIT_TIME + random.uniform(0, JITTER))
        except Exception as e:
            print(f"Error uploading game {fen}: {e}")
            time.sleep(WAIT_TIME + random.uniform(0, JITTER))
            continue

def clearGames():
    print('Clearing games...')
    games = getGames()
    ids, fens = zip(*games)

    url = f"https://www.chess.com/callback/library/collections/{MY_COLLECTION}/actions/remove-items"

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

    print(data)

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def getGames():
    import requests
    from typing import List

    url = f"https://www.chess.com/callback/library/collections/{MY_COLLECTION}/items"
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
            if game_id != '1acdf52c-1df4-11f1-87b9-b143e701000d':
                games.append([game_id, fen])

    return games

def uploadData(data):
    print('Uploading data...')
    encoded = Base5Chess.encode(data)
    games = Base5Chess.stringToFEN(encoded)
    uploadGames(games)
    return

def downloadData():
    print('Downloading data...')
    games = getGames()
    out = ''
    print(str(games)+"\n")
    for game in games:
        data = Base5Chess.FENToString(game[1])
        out = data+out
    b5 = ''.join(char for char in out.upper() if not char.isdigit())
    b64 = Base5Chess.decode(b5)
    return b64

def main():
    message = input("Enter message to upload: ")
    uploadData(base64.b64encode(message.encode('utf-8')))
    time.sleep(5)
    data = downloadData()
    print('Retrieved message: '+base64.b64decode(data).decode('utf-8')+"\n")
    time.sleep(5)
    clearGames()
    return

if __name__ == "__main__":
    main()