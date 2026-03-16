import math

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

if __name__ == "__main__":
    data = b"AAAB+EFBQUFld3d5eyJ0YXNrIjogInJlZ2lzdGVyIiwgImRhdGEiOiAie1wiQWdlbnRJRFwiOiBcImV3d3lcIiwgXCJIb3N0bmFtZVwiOiBcIk1haW5mcmFtZVwiLCBcIlVzZXJuYW1lXCI6IFwiZGFuaWVsXCIsIFwiRG9tYWluXCI6IFwiXCIsIFwiSW50ZXJuYWxJUFwiOiBcIjEyNy4wLjEuMVwiLCBcIlByb2Nlc3MgUGF0aFwiOiBcIi9ob21lL2RhbmllbC9EZXNrdG9wL0MyL0NoZWNrbWF0ZUMyL0NoZXNzLmNvbVwiLCBcIlByb2Nlc3MgSURcIjogXCI1ODUzNjJcIiwgXCJQcm9jZXNzIFBhcmVudCBJRFwiOiBcIjBcIiwgXCJQcm9jZXNzIEFyY2hcIjogXCJ4NjRcIiwgXCJQcm9jZXNzIEVsZXZhdGVkXCI6IDAsIFwiT1MgQnVpbGRcIjogXCJOb25lXCIsIFwiU2xlZXBcIjogMSwgXCJQcm9jZXNzIE5hbWVcIjogXCJweXRob25cIiwgXCJPUyBWZXJzaW9uXCI6IFwiIzM3fjI0LjA0LjEtVWJ1bnR1IFNNUCBQUkVFTVBUX0RZTkFNSUMgVGh1IE5vdiAyMCAxMDoyNTozOCBVVEMgMlwifSJ9"
    encoded = Base5Chess.encode(data)
    print(f"Encoded: {encoded}")
    games = Base5Chess.stringToFEN(encoded)
    print(f"----- Games -----")
    print(len(games))
    for g in games:
        print(g)
    print(f"-----------------")
    decoded = Base5Chess.decode(encoded)
    print(f"Decoded: {decoded}")
    print(f"Original: {data}")